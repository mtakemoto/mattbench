"""Benchmark suite registry.

Every module in this package that defines a module-level ``SUITE`` is a
benchmark suite. The execution plan, worker, suite runner, report and console
discover suites from here, so adding one needs only a new module and its
fixture file. Nothing outside this package may name a specific suite.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import sys
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from inspect_ai import Task

ROOT = Path(__file__).resolve().parents[1]
INSPECT_LOG_ROOT = ROOT / "artifacts/inspect"
BASE_VARIANT = "base"


@dataclass(frozen=True)
class Case:
    """One validated fixture row, frozen as canonical JSON so plans can be compared exactly."""

    suite: str
    id: str
    name: str
    max_model_calls: int
    data_json: str

    @property
    def data(self) -> dict[str, Any]:
        return json.loads(self.data_json)

    def to_dict(self) -> dict[str, Any]:
        return {"suite": self.suite, "id": self.id, "name": self.name,
                "maxModelCalls": self.max_model_calls, "data": self.data}


@dataclass(frozen=True)
class RunTarget:
    """Model endpoint settings a suite needs to build a child-process command."""

    source: str
    model: str
    run_id: str
    plan_file: Path
    base_url: str = ""
    cap_usd: float | None = None
    progress_file: Path | None = None
    """Shared progress record; only suites with a multi-phase lifecycle write to it."""

    def arguments(self) -> list[str]:
        arguments = ["--source", self.source, "--model", self.model, "--run-id", self.run_id,
                     "--plan-file", str(self.plan_file)]
        if self.base_url:
            arguments += ["--base-url", self.base_url]
        if self.source == "openrouter" and self.cap_usd is not None:
            arguments += ["--cap-usd", str(self.cap_usd)]
        return arguments


class Suite(ABC):
    """A group of cases that share a fixture file, an Inspect task and a way to run.

    Subclasses set the class attributes and implement ``parse_row`` and
    ``task``. Override ``command`` or ``timeout_seconds`` only when the suite
    needs its own process lifecycle, such as disposable containers.
    """

    id: str
    label: str
    description: str
    fixture: str
    variants: tuple[str, ...] = (BASE_VARIANT,)
    """Prompt variants the suite can run; every suite supports the base prompt."""
    position: int = 100
    """Run and display order; lower runs first."""
    isolated_cases: bool = False
    """True when each case needs its own process and fresh environment."""
    max_tokens: int = 512
    seconds_per_call: int = 125
    startup_seconds: int = 60

    @abstractmethod
    def parse_row(self, row: dict[str, Any]) -> Case:
        """Validate one fixture row and return its frozen case; raise ValueError on bad data."""

    @abstractmethod
    def task(self, cases: tuple[Case, ...], variant: str) -> Task:
        """Build the Inspect task for these cases under one prompt variant."""

    def fixture_path(self) -> Path:
        return ROOT / self.fixture

    def load_cases(self, path: Path | None = None) -> tuple[Case, ...]:
        source = path or self.fixture_path()
        try:
            rows = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Cannot read {self.id} fixture {source.name}: {error}") from error
        if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
            raise ValueError(f"{self.id} fixture must be a nonempty JSON array of objects.")
        cases = tuple(self.parse_row(row) for row in rows)
        duplicates = [case_id for case_id, count in Counter(case.id for case in cases).items() if count > 1]
        if duplicates:
            raise ValueError(f"{self.id} fixture repeats case IDs: {', '.join(sorted(duplicates))}")
        return cases

    def make_case(self, row: dict[str, Any], *, name: str, max_model_calls: int) -> Case:
        case_id = require_text(row, "id", self.id)
        if type(max_model_calls) is not int or not 1 <= max_model_calls <= 100:
            raise ValueError(f"{self.id} case {case_id}: model-call ceiling must be an integer from 1 to 100.")
        return Case(self.id, case_id, name, max_model_calls,
                    json.dumps(row, sort_keys=True, separators=(",", ":")))

    def log_dir(self, run_id: str) -> Path:
        return INSPECT_LOG_ROOT / self.id / run_id

    def timeout_seconds(self, model_calls: int) -> int:
        """Outer deadline for one child process that makes at most ``model_calls`` generations."""
        return model_calls * self.seconds_per_call + self.startup_seconds

    def command(self, cases: tuple[Case, ...], target: RunTarget, model_calls: int) -> list[str]:
        """Child process that evaluates ``cases`` from the frozen plan."""
        case_arguments = [argument for case in cases for argument in ("--case", case.id)]
        return [sys.executable, str(ROOT / "scripts/run-inspect-cases.py"), "--suite", self.id,
                *case_arguments, "--max-calls", str(model_calls), *target.arguments()]

    def describe(self) -> dict[str, Any]:
        """Non-secret catalog entry for the console."""
        return {"id": self.id, "label": self.label, "description": self.description,
                "variants": list(self.variants), "isolatedCases": self.isolated_cases,
                "cases": [{"id": case.id, "name": case.name, "maxModelCalls": case.max_model_calls}
                          for case in self.load_cases()]}


def require_text(row: dict[str, Any], field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} case {row.get('id', '?')}: {field} must be a nonempty string.")
    return value


@cache
def registry() -> dict[str, Suite]:
    """Discover every suite module in this package, ordered by position then ID."""
    found: list[Suite] = []
    for module_info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        suite = getattr(module, "SUITE", None)
        if isinstance(suite, Suite):
            found.append(suite)
    ids = [suite.id for suite in found]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Two suite modules declare the same suite ID.")
    return {suite.id: suite for suite in sorted(found, key=lambda suite: (suite.position, suite.id))}


def get_suite(suite_id: str) -> Suite:
    try:
        return registry()[suite_id]
    except KeyError:
        raise ValueError(f"Unknown benchmark suite: {suite_id}") from None
