"""Inspect pilot tasks that are not benchmark suites: the disposable coding repair.

Benchmark suite tasks live in suites/<suite>/task.py.
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.agent import react
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import TaskState
from inspect_ai.tool import bash
from inspect_ai.util import sandbox

ROOT = Path(__file__).resolve().parent


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
