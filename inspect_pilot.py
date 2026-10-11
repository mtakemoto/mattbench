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
from inspect_ai.solver import TaskState, generate
from inspect_ai.tool import bash
from inspect_ai.tool import mcp_server_stdio, mcp_tools
from inspect_ai.util import sandbox


ROOT = Path(__file__).resolve().parent


@task
def smoke() -> Task:
    rows = json.loads((ROOT / "tasks/smoke.json").read_text())
    return Task(
        dataset=[
            Sample(
                id=row["id"],
                input=row["prompt"],
                target=row["expected"],
                metadata={"category": row["category"], "fixture": "tasks/smoke.json"},
            )
            for row in rows
        ],
        solver=generate(),
        scorer=match(location="exact"),
        display_name="Mattbench smoke: pinned no-tool questions",
        version="1",
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
def synthetic_ha_state() -> object:
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
        coordinator = get_state("climate.north_room_coordinator")
        head = get_state("climate.north_room_head")
        correct = (
            coordinator["attributes"].get("temperature") == 68
            and head["attributes"].get("temperature") == 74
        )
        return Score(
            value=1 if correct else 0,
            explanation=(
                "Coordinator target changed to 68; indoor head remained at 74."
                if correct else "Final synthetic climate targets did not match the pinned assertion."
            ),
        )
    return score


@task
def ha_chained() -> Task:
    container = os.environ["MATTBENCH_SYNTHETIC_MCP_CONTAINER"]
    server = mcp_server_stdio(name="synthetic_ha_mcp", command="docker", args=["exec", "-i", container, "ha-mcp"])
    return Task(
        dataset=[Sample(
            id="north_room_coordinator_target",
            input=(
                "In the fictional North Room, find the Coordinator climate entity, read its "
                "current target, set only that Coordinator's target temperature to 68 °F, "
                "then read back both the Coordinator and Indoor Head. Do not change the "
                "Indoor Head. Use the Home Assistant tools for each step."
            ),
            target="Coordinator target 68; Indoor Head target unchanged at 74",
            metadata={"category": "ha_chained_pilot", "fixture": "fixtures/ha/inspect-climate.yaml"},
        )],
        solver=react(tools=[mcp_tools(server, tools=["ha_search", "ha_get_state", "ha_call_service"])]),
        scorer=synthetic_ha_state(),
        turn_limit=10,
        time_limit=180,
        display_name="Mattbench HA: real ha-mcp against disposable Synthetic Home",
        version="1",
    )
