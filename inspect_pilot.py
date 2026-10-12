"""Small Inspect AI replacement pilot using pinned mattbench fixtures."""

import json
import os
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

from inspect_ai import Task, task
from inspect_ai.agent import react
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, match, scorer
from inspect_ai.solver import TaskState, generate, system_message
from inspect_ai.tool import bash
from inspect_ai.tool import mcp_server_stdio, mcp_tools
from inspect_ai.util import sandbox


ROOT = Path(__file__).resolve().parent


@task
def smoke(prompt_variant: str = "base") -> Task:
    if prompt_variant not in {"base", "careful"}:
        raise ValueError("Unknown smoke prompt variant")
    rows = json.loads((ROOT / "tasks/smoke.json").read_text())
    return Task(
        dataset=[
            Sample(
                id=row["id"],
                input=row["prompt"],
                target=row["expected"],
                metadata={"category": row["category"], "fixture": "tasks/smoke.json", "prompt_variant": prompt_variant},
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
        def get_state(entity_id: str) -> dict:
            script = (
                "import json,sys,urllib.request; "
                "p=json.load(sys.stdin); "
                "r=urllib.request.Request('http://127.0.0.1:8123/api/states/'+p['entity'], "
                "headers={'Authorization':'Bearer '+p['token']}); "
                "print(urllib.request.urlopen(r,timeout=10).read().decode())"
            )
            result = subprocess.run(
                ["docker", "exec", "-i", container, "python", "-c", script],
                input=json.dumps({"entity": entity_id, "token": token}),
                text=True, capture_output=True, check=True,
            )
            return json.loads(result.stdout)
        def matches(actual: dict, wanted: dict) -> bool:
            return all(
                matches(actual.get(key, {}), value) if isinstance(value, dict)
                else actual.get(key) == value
                for key, value in wanted.items()
            )
        correct = all(matches(get_state(entity_id), wanted) for entity_id, wanted in case["expected"].items())
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


def safe_ha_trace(messages: list, case: dict) -> tuple[bool, str]:
    """Check each requested write and the readback sequence, including failed calls."""
    calls = [call for message in messages for call in (getattr(message, "tool_calls", None) or [])]
    action = case["action"]
    expected_data = dict(action["data"])
    expected_entity = expected_data.pop("entity_id")
    writes = []
    for index, call in enumerate(calls):
        if call.function != "ha_call_service":
            continue
        args = call.arguments
        if set(args) - {"domain", "service", "entity_id", "data", "return_response", "wait"}:
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
        writes.append(index)
    if not writes:
        return False, "The target service was not called."
    first_write = writes[0]
    if case.get("require_search") and not any(call.function == "ha_search" for call in calls[:first_write]):
        return False, "No entity search preceded the write."
    for entity in case.get("require_initial_read", []):
        if not any(call.function == "ha_get_state" and call.arguments.get("entity_id") == entity
                   for call in calls[:first_write]):
            return False, "A required initial state read was missing."
    for entity in case["expected"]:
        if not any(call.function == "ha_get_state" and call.arguments.get("entity_id") == entity
                   for call in calls[writes[-1] + 1:]):
            return False, "A required state readback was missing."
    return True, "Tool sequence matched the pinned case."


def ha_cases() -> dict[str, dict]:
    cases = json.loads((ROOT / "tasks/inspect-ha-cases.json").read_text())
    return {case["id"]: case for case in cases}


@task
def ha_case(case_id: str = "mxz_coordinator_target") -> Task:
    case = ha_cases()[case_id]
    container = os.environ["MATTBENCH_SYNTHETIC_MCP_CONTAINER"]
    server = mcp_server_stdio(name="synthetic_ha_mcp", command="docker", args=["exec", "-i", container, "ha-mcp"])
    return Task(
        dataset=[Sample(
            id=case_id,
            input=case["prompt"],
            target=case["target"],
            metadata={"category": "ha_chained", "fixture": case["fixture"], "prompt_variant": "base"},
        )],
        solver=react(tools=[mcp_tools(server, tools=["ha_search", "ha_get_state", "ha_call_service"])]),
        scorer=synthetic_ha_state(case),
        turn_limit=case["max_model_calls"],
        time_limit=180,
        display_name=f"Mattbench HA: {case['name']}",
        version="4",
    )


def ha_chained() -> Task:
    """Historical pilot alias; use ha_case for new runs."""
    return ha_case()
