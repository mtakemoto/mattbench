"""Pick the laptop that fits a buyer persona from a fixed ten-laptop catalog."""

from typing import Any

from suites import Case, Suite, require_text


class LaptopShoppingSuite(Suite):
    id = "laptop_shopping"
    label = "Laptop shopping"
    description = "Match buyer personas to one catalog laptop, or answer ALL or NONE for trick questions."
    fixture = "tasks/laptop-shopping.json"
    position = 30
    # Reasoning models spend hundreds of tokens before the final ANSWER line;
    # 512 truncated every answer in the first run.
    max_tokens = 4096

    def parse_row(self, row: dict[str, Any]) -> Case:
        for field in ("persona", "expected"):
            require_text(row, field, self.id)
        return self.make_case(row, name=row.get("title") or row["id"], max_model_calls=1)

    def task(self, cases: tuple[Case, ...], variant: str):
        from inspect_laptops import laptop_shopping

        return laptop_shopping(cases=[case.data for case in cases])


SUITE = LaptopShoppingSuite()
