"""Small Inspect AI replacement pilot using pinned mattbench fixtures."""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from inspect_ai import Task, task
from inspect_ai.agent import react
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, match, scorer
from inspect_ai.solver import TaskState, generate, system_message
from inspect_ai.tool import bash
from inspect_ai.tool import mcp_server_stdio, mcp_tools
from inspect_ai.util import sandbox

from scripts.bounded_process import run_bounded_async
from scripts.execution_plan import build_plan

if TYPE_CHECKING:
    from scripts.execution_plan import SmokeCase


ROOT = Path(__file__).resolve().parent


@task
def smoke(prompt_variant: str = "base", rows: tuple["SmokeCase", ...] | None = None) -> Task:
    if prompt_variant not in {"base", "careful"}:
        raise ValueError("Unknown smoke prompt variant")
    if rows is None:
        rows = json.loads((ROOT / "tasks/smoke.json").read_text())
    return Task(
        dataset=[
            Sample(
                id=row["id"] if isinstance(row, dict) else row.id,
                input=row["prompt"] if isinstance(row, dict) else row.prompt,
                target=row["expected"] if isinstance(row, dict) else row.expected,
                metadata={"category": row["category"] if isinstance(row, dict) else row.category,
                          "fixture": "tasks/smoke.json", "prompt_variant": prompt_variant},
            )
            for row in rows
        ],
        solver=(
            generate()
            if prompt_variant == "base"
            else [system_message("Think through the practical goal and any relevant constraints before answering. Follow the user's requested answer format exactly."), generate()]
        ),
        scorer=match(location="exact"),
        display_name="Mattbench smoke: pinned no-tool questions",
        version="2",
    )


@scorer(metrics=[accuracy()])
def clamp_state() -> object:
    async def score(state: TaskState, target: Target) -> Score:
        checks = (
            "from clamp import clamp; "
            "assert clamp(-4, 0, 10) == 0; "
            "assert clamp(6, 0, 10) == 6; "
            "assert clamp(17, 0, 10) == 10; "
            "assert clamp(2, 2, 2) == 2"
        )
        result = await sandbox().exec(["python", "-c", checks], timeout=10)
        return Score(
            value=1 if result.success else 0,
            explanation="Hidden boundary and interior checks passed." if result.success else "Hidden clamp checks failed.",
        )

    return score


@task
def coding() -> Task:
    return Task(
        dataset=[
            Sample(
                id="clamp_fix",
                input=(
                    "Fix clamp(value, low, high) in clamp.py so it returns value "
                    "bounded by low and high. Preserve the function signature. "
                    "Inspect the file, make the smallest correction, and check your work."
                ),
                target="Correct clamp behavior",
                files={"clamp.py": str(ROOT / "fixtures/coding/clamp.py")},
                metadata={"category": "coding_pilot", "fixture": "fixtures/coding/clamp.py"},
            )
        ],
        solver=react(tools=[bash(timeout=15)]),
        scorer=clamp_state(),
        sandbox=("docker", str(ROOT / "inspect/compose.yaml")),
        turn_limit=6,
        time_limit=120,
        display_name="Mattbench coding: disposable clamp repair",
        version="1",
    )


@scorer(metrics=[accuracy()])
def synthetic_ha_state(case: dict) -> object:
    async def score(state: TaskState, target: Target) -> Score:
        container = os.environ["MATTBENCH_SYNTHETIC_HA_CONTAINER"]
        token = os.environ["MATTBENCH_SYNTHETIC_HA_TOKEN"]
        async def get_state(entity_id: str) -> dict:
            script = (
                "import json,sys,urllib.request; "
                "p=json.load(sys.stdin); "
                "r=urllib.request.Request('http://127.0.0.1:8123/api/states/'+p['entity'], "
                "headers={'Authorization':'Bearer '+p['token']}); "
                "print(urllib.request.urlopen(r,timeout=10).read().decode())"
            )
            result = await run_bounded_async(
                ["docker", "exec", "-i", container, "python", "-c", script],
                timeout=20, input=json.dumps({"entity": entity_id, "token": token}),
                text=True, capture_output=True, check=True,
            )
            return json.loads(result.stdout)
        correct = True
        for entity_id, wanted in case["expected"].items():
            if not _ha_matches(await get_state(entity_id), wanted):
                correct = False
        trace_ok, trace_reason = safe_ha_trace(state.messages, case)
        return Score(
            value=1 if correct and trace_ok else 0,
            explanation=("Final synthetic states and tool sequence matched pinned assertions."
                         if correct and trace_ok else
                         "Final synthetic states did not match pinned assertions." if not correct else trace_reason),
            metadata={"state_correct": correct, "trace_valid": trace_ok,
                      "trace_reason": trace_reason if not trace_ok else None},
        )
    return score


def _ha_result(message: object) -> dict | None:
    """Decode a successful ha-mcp result; Inspect tool errors and payload errors fail closed."""
    if getattr(message, "error", None) or not getattr(message, "text", "").strip():
        return None
    try:
        payload = json.loads(message.text)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if (payload.get("success") is False or payload.get("isError") is True
            or payload.get("is_error") is True or payload.get("error")
            or payload.get("status") in ("error", "failed")):
        return None
    if isinstance(payload.get("data"), dict) and (
        payload["data"].get("error") or payload["data"].get("success") is False
    ):
        return None
    return payload


def _ha_matches(actual: dict, wanted: dict) -> bool:
    if not isinstance(actual, dict):
        return False
    return all(
        _ha_matches(actual.get(key, {}), value) if isinstance(value, dict)
        else actual.get(key) == value
        for key, value in wanted.items()
    )

def _ha_search_found(payload: object, entity: str) -> bool:
    if isinstance(payload, dict):
        return payload.get("entity_id") == entity or any(
            _ha_search_found(value, entity)
            for key, value in payload.items() if key not in {"query", "metadata"}
        )
    if isinstance(payload, list):
        return any(_ha_search_found(value, entity) for value in payload)
    return False



def safe_ha_trace(messages: list, case: dict) -> tuple[bool, str]:
    """Require correlated successful tool results before dependent requests."""
    action = case["action"]
    expected_data = dict(action["data"])
    expected_entity = expected_data.pop("entity_id")
    initial = set(case.get("require_initial_read", []))
    readbacks = set(case["expected"])
    found = not case.get("require_search", False)
    observed: set[str] = set()
    verified: set[str] = set()
    write_epoch = 0
    completed_write_epoch = 0
    pending: dict[str, tuple[str, str | list[str] | None, int, bool]] = {}
    seen: set[str] = set()
    for message in messages:
        if getattr(message, "role", None) == "assistant":
            for call in message.tool_calls or []:
                if not call.id or call.id in seen:
                    return False, "A tool request lacked a unique call ID."
                seen.add(call.id)
                if call.function == "ha_call_service":
                    args = call.arguments
                    if not isinstance(args, dict) or set(args) - {
                        "domain", "service", "entity_id", "data", "return_response", "wait"
                    }:
                        return False, "A service call included an unapproved target or parameter."
                    data = args.get("data") or {}
                    try:
                        data = json.loads(data) if isinstance(data, str) else data
                    except json.JSONDecodeError:
                        return False, "A service call contained invalid data."
                    if not isinstance(data, dict):
                        return False, "A service call contained invalid data."
                    data = dict(data)
                    nested_entity = data.pop("entity_id", None)
                    direct_entity = args.get("entity_id")
                    if direct_entity and nested_entity and direct_entity != nested_entity:
                        return False, "A service call contained conflicting targets."
                    effective_entity = direct_entity or nested_entity
                    if (args.get("domain"), args.get("service"), effective_entity, data) != (
                        action["domain"], action["service"], expected_entity, expected_data
                    ):
                        return False, "A service call did not match the allowed target and action."
                    if not found:
                        return False, "No successful relevant entity search preceded the write."
                    if not initial <= observed:
                        return False, "A required initial state read was missing or unsuccessful."
                    write_epoch += 1
                    completed_write_epoch = 0
                    verified.clear()
                    pending[call.id] = (call.function, None, write_epoch, False)
                elif call.function in {"ha_get_state", "ha_search"}:
                    entity = call.arguments.get("entity_id") if isinstance(call.arguments, dict) else None
                    fields = call.arguments.get("fields") if isinstance(call.arguments, dict) else None
                    if isinstance(fields, str):
                        fields = [fields]
                    projected = (isinstance(fields, list) and all(isinstance(field, str) for field in fields)
                                 and "state" in fields and "entity_id" not in fields)
                    pending[call.id] = (call.function, entity, completed_write_epoch, projected)
        elif getattr(message, "role", None) == "tool":
            entry = pending.pop(message.tool_call_id, None)
            if entry is None:
                return False, "A tool result did not match a requested call ID."
            function, entity, request_epoch, projected = entry
            if message.function != function:
                return False, "A tool result did not match its requested function."
            result = _ha_result(message)
            if result is None:
                continue
            if function == "ha_call_service":
                if request_epoch == write_epoch and result.get("success") is True:
                    completed_write_epoch = write_epoch
            elif function == "ha_search":
                found = _ha_search_found(result.get("data", result.get("results", result)), expected_entity)
            elif function == "ha_get_state":
                entities = (entity,) if isinstance(entity, str) else entity if isinstance(entity, list) else ()
                if not entities or not all(isinstance(item, str) for item in entities):
                    continue
                bulk = isinstance(entity, list)
                records = result.get("states") if bulk else {entity: result.get("data")}
                if not isinstance(records, dict):
                    continue
                for requested in entities:
                    state = records.get(requested)
                    if (not isinstance(state, dict) or state.get("error") or state.get("success") is False
                            or state.get("entity_id", requested if bulk or projected else None) != requested
                            or not isinstance(state.get("state"), str)):
                        continue
                    if (request_epoch != 0 and request_epoch == completed_write_epoch
                            and requested in readbacks and _ha_matches(state, case["expected"][requested])):
                        verified.add(requested)
                    elif request_epoch == 0 and completed_write_epoch == 0:
                        observed.add(requested)
    if pending:
        return False, "A requested tool result was missing."
    if not completed_write_epoch:
        return False, "The target service did not complete successfully."
    if not readbacks <= verified:
        return False, "A required successful state readback was missing."
    return True, "Tool sequence matched the pinned case."


def ha_cases() -> dict[str, dict]:
    return {case.id: case.to_dict() for case in build_plan(case_id="all").ha_cases}


@task
def ha_case(case_id: str = "mxz_coordinator_target", case: dict | None = None) -> Task:
    if case is None:
        case = ha_cases()[case_id]
    container = os.environ["MATTBENCH_SYNTHETIC_MCP_CONTAINER"]
    server = mcp_server_stdio(name="synthetic_ha_mcp", command="docker", args=["exec", "-i", container, "ha-mcp"])
    return Task(
        dataset=[Sample(
            id=case_id,
            input=case["prompt"],
            target=case["target"],
            metadata={"category": case["category"], "fixture": case["fixture"], "prompt_variant": "base"},
        )],
        solver=react(tools=[mcp_tools(server, tools=["ha_search", "ha_get_state", "ha_call_service"])]),
        scorer=synthetic_ha_state(case),
        turn_limit=case["max_model_calls"],
        time_limit=180,
        display_name=f"Mattbench HA: {case['name']}",
        version="4",
    )

