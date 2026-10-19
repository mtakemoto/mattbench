"""Pinned no-tool reasoning questions with an exact short answer."""

from typing import Any

from suites import BASE_VARIANT, Case, Suite, require_text

FIELDS = ("id", "prompt", "expected", "category")


class SmokeSuite(Suite):
    id = "smoke"
    label = "Smoke questions"
    description = "Quick no-tool reasoning checks with one exact answer each."
    fixture = "tasks/smoke.json"
    variants = (BASE_VARIANT, "careful")
    position = 10

    def parse_row(self, row: dict[str, Any]) -> Case:
        if set(row) != set(FIELDS):
            raise ValueError(f"Smoke rows require exactly {', '.join(FIELDS)}.")
        for field in FIELDS:
            require_text(row, field, self.id)
        return self.make_case(row, name=row["id"].replace("_", " ").capitalize(), max_model_calls=1)

    def task(self, cases: tuple[Case, ...], variant: str):
        from inspect_pilot import smoke

        return smoke(variant, rows=tuple(case.data for case in cases))


SUITE = SmokeSuite()
