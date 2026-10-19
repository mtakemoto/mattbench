"""Inspect AI task definition for laptop shopping benchmark cases."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import TaskState, generate, system_message

from suites.laptop_shopping.grader import build_prompt_for_case, grade_case, load_catalog, load_tasks



@scorer(metrics=[accuracy()])
def laptop_choice_scorer() -> object:
    """Score model answers against expected laptop ID, ALL, or NONE targets."""

    async def score(state: TaskState, target: Target) -> Score:
        case_id = state.metadata.get("case_id", "")
        case = state.metadata.get("case_data", {})
        model_output = state.output.completion if state.output else ""

        graded = grade_case(case, model_output)
        value = 1 if graded["passed"] else 0
        explanation = (
            f"Expected '{graded['expected']}', extracted '{graded['extracted']}'. "
            f"Grading {'passed' if graded['passed'] else 'failed'}."
        )

        return Score(
            value=value,
            explanation=explanation,
            metadata={
                "case_id": case_id,
                "expected": graded["expected"],
                "extracted": graded["extracted"],
                "reasoning": graded.get("reasoning"),
            },
        )

    return score


@task
def laptop_shopping(cases: Optional[List[Dict[str, Any]]] = None) -> Task:
    """Create Inspect AI Task for laptop shopping evaluations."""
    catalog = load_catalog()
    if cases is None:
        cases = load_tasks()

    samples = []
    for c in cases:
        prompt_text = build_prompt_for_case(c, catalog)
        sample = Sample(
            id=c["id"],
            input=prompt_text,
            target=c["expected"],
            metadata={
                "case_id": c["id"],
                "category": c.get("category", "laptop_recommendation"),
                "persona_number": c.get("persona_number"),
                "case_data": c,
            },
        )
        samples.append(sample)

    return Task(
        dataset=samples,
        solver=[
            system_message(
                "You are an expert computing hardware advisor. Analyze all laptop specifications, "
                "display details, operating systems, battery life, dimensions, and image descriptions "
                "carefully to match the user's specific persona. Answer with a single laptop ID, ALL, or NONE."
            ),
            generate(),
        ],
        scorer=laptop_choice_scorer(),
        display_name="Mattbench: Laptop Shopping Benchmark",
        version="1",
    )
