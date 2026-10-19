"""Inspect task for the smoke suite: exact short answers, optionally with a careful system note."""

import json

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import match
from inspect_ai.solver import generate, system_message

from suites.smoke import SUITE

@task
def smoke(prompt_variant: str = "base", rows: tuple[dict, ...] | None = None) -> Task:
    """Exact-answer questions; pass frozen plan rows so a later fixture edit cannot change a run."""
    if prompt_variant not in {"base", "careful"}:
        raise ValueError("Unknown smoke prompt variant")
    if rows is None:
        rows = json.loads(SUITE.fixture_path().read_text())
    return Task(
        dataset=[
            Sample(
                id=row["id"], input=row["prompt"], target=row["expected"],
                metadata={"category": row["category"], "fixture": SUITE.fixture, "prompt_variant": prompt_variant},
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
