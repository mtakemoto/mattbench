"""Chained Home Assistant changes through real ha-mcp against a disposable Synthetic Home."""

import sys
from typing import Any

from suites import ROOT, Case, RunTarget, Suite, require_text


class SmartHomeSuite(Suite):
    id = "smart_home"
    label = "Smart home"
    description = "Find, change and read back entities through real ha-mcp in a fresh synthetic home."
    fixture = "tasks/inspect-ha-cases.json"
    position = 20
    isolated_cases = True
    case_deadline_seconds = 600
    """Covers container setup, evaluation and teardown; see run-inspect-ha-pilot.py."""

    def parse_row(self, row: dict[str, Any]) -> Case:
        case_id = require_text(row, "id", self.id)
        for field in ("name", "prompt", "target", "category", "fixture"):
            require_text(row, field, self.id)
        for field in ("initial", "expected", "action"):
            if not isinstance(row.get(field), dict):
                raise ValueError(f"{self.id} case {case_id}: {field} must be an object.")
        for field in ("initial", "expected"):
            if not row[field] or any(not isinstance(entity, str) or "." not in entity or not isinstance(state, dict)
                                     for entity, state in row[field].items()):
                raise ValueError(f"{self.id} case {case_id}: {field} requires entity-to-state assertions.")
        action = row["action"]
        if (not all(isinstance(action.get(key), str) and action[key] for key in ("domain", "service"))
                or not isinstance(action.get("data"), dict)
                or action["data"].get("entity_id") not in row["expected"]):
            raise ValueError(f"{self.id} case {case_id}: action requires a service and expected entity target.")
        if "require_search" in row and type(row["require_search"]) is not bool:
            raise ValueError(f"{self.id} case {case_id}: require_search must be boolean.")
        reads = row.get("require_initial_read", [])
        if not isinstance(reads, list) or any(entity not in row["initial"] for entity in reads):
            raise ValueError(f"{self.id} case {case_id}: initial reads must reference pinned initial entities.")
        return self.make_case(row, name=row["name"], max_model_calls=row.get("max_model_calls"))

    def task(self, cases: tuple[Case, ...], variant: str):
        from inspect_pilot import ha_case

        (case,) = cases
        return ha_case(case.id, case=case.data)

    def timeout_seconds(self, model_calls: int) -> int:
        return self.case_deadline_seconds

    def command(self, cases: tuple[Case, ...], target: RunTarget, model_calls: int) -> list[str]:
        (case,) = cases
        return [sys.executable, str(ROOT / "scripts/run-inspect-ha-pilot.py"), "--case", case.id,
                "--max-calls", str(model_calls), *target.arguments(),
                *(["--progress-file", str(target.progress_file)] if target.progress_file else [])]


SUITE = SmartHomeSuite()
