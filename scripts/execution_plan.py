"""Freeze which cases a run evaluates and how many model generations it may make.

A plan is resolved once from the registered suites (see ``suites/``), saved
next to the run, and reloaded by every child process so a fixture edit during
a run cannot change what is evaluated or the confirmed call ceiling.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from scripts.run_inspect_settings import SOURCES, is_free_model, resolve_base_url, validate_cap, validate_model
from suites import BASE_VARIANT, Case, RunTarget, Suite, get_suite, registry

PLAN_VERSION = 2
SELECT_ALL = "all"
CHILD_TERMINATE_GRACE_SECONDS = 60
"""Time a timed-out child gets to clean up after SIGTERM."""
ORCHESTRATION_SECONDS = 120
"""Worker overhead outside child processes: plan loading, progress, scoring."""


@dataclass(frozen=True)
class PlanEntry:
    """One child process: a whole suite, or a single case of a suite with isolated cases."""

    id: str
    label: str
    suite: Suite
    cases: tuple[Case, ...]
    variants: tuple[str, ...]

    @property
    def model_calls(self) -> int:
        return sum(case.max_model_calls for case in self.cases) * len(self.variants)

    @property
    def expected_samples(self) -> Counter:
        """Inspect sample IDs this entry must log: one per case per prompt variant."""
        return Counter(case.id for _ in self.variants for case in self.cases)

    @property
    def timeout_seconds(self) -> int:
        return self.suite.timeout_seconds(self.model_calls)

    def command(self, target: RunTarget) -> list[str]:
        return self.suite.command(self.cases, target, self.model_calls)


@dataclass(frozen=True)
class ExecutionPlan:
    variants: tuple[str, ...]
    cases: tuple[Case, ...]

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("Execution plan must contain at least one case.")
        if not self.variants or len(set(self.variants)) != len(self.variants):
            raise ValueError("Execution plan needs distinct prompt variants.")
        for suite_id in dict.fromkeys(case.suite for case in self.cases):
            unsupported = set(self.variants) - set(get_suite(suite_id).variants)
            if unsupported:
                raise ValueError(f"{get_suite(suite_id).label} does not support the "
                                 f"{', '.join(sorted(unsupported))} prompt; choose the base prompt.")
        ids = [(case.suite, case.id) for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Execution plan repeats a case.")

    @property
    def max_calls(self) -> int:
        return sum(entry.model_calls for entry in self.entries)

    @property
    def deadline_seconds(self) -> int:
        """Outer bound for the whole run, including every child's cleanup grace."""
        return ORCHESTRATION_SECONDS + sum(entry.timeout_seconds + CHILD_TERMINATE_GRACE_SECONDS
                                           for entry in self.entries)

    @property
    def entries(self) -> tuple[PlanEntry, ...]:
        """Child processes in suite order; isolated suites get one entry per case."""
        entries = []
        for suite_id, suite in registry().items():
            cases = tuple(case for case in self.cases if case.suite == suite_id)
            if not cases:
                continue
            if suite.isolated_cases:
                entries.extend(PlanEntry(case.id, case.name, suite, (case,), self.variants) for case in cases)
            else:
                entries.append(PlanEntry(suite_id, suite.label, suite, cases, self.variants))
        return tuple(entries)

    def entry(self, suite_id: str, case_ids: Iterable[str] = ()) -> PlanEntry:
        """Find the entry a child process was launched for."""
        wanted = tuple(case_ids)
        for entry in self.entries:
            if entry.suite.id == suite_id and (not wanted or wanted == tuple(case.id for case in entry.cases)):
                return entry
        raise ValueError(f"No {suite_id} entry with cases {', '.join(wanted) or '(all)'} in the frozen plan.")

    def to_dict(self) -> dict[str, Any]:
        return {"version": PLAN_VERSION, "variants": list(self.variants),
                "cases": [case.to_dict() for case in self.cases], "maxCalls": self.max_calls}


def build_plan(selection: Iterable[str] = (SELECT_ALL,), variants: Iterable[str] = (BASE_VARIANT,), *,
               fixture_paths: Mapping[str, Path] | None = None) -> ExecutionPlan:
    """Resolve suite IDs, case IDs or ``all`` against the current fixtures."""
    tokens = list(dict.fromkeys(selection))
    if not tokens or not all(isinstance(token, str) and token for token in tokens):
        raise ValueError("Select at least one suite or case.")
    loaded: dict[str, tuple[Case, ...]] = {}

    def cases_of(suite_id: str) -> tuple[Case, ...]:
        if suite_id not in loaded:
            loaded[suite_id] = get_suite(suite_id).load_cases((fixture_paths or {}).get(suite_id))
        return loaded[suite_id]

    chosen: list[Case] = []
    for token in tokens:
        if token == SELECT_ALL:
            chosen.extend(case for suite_id in registry() for case in cases_of(suite_id))
        elif token in registry():
            chosen.extend(cases_of(token))
        else:
            matches = [case for suite_id in registry() for case in cases_of(suite_id) if case.id == token]
            if len(matches) != 1:
                raise ValueError(f"Unknown or ambiguous suite or case ID: {token}")
            chosen.extend(matches)
    unique = dict.fromkeys(chosen)
    return ExecutionPlan(tuple(variants), tuple(unique))


def load_plan(path: Path) -> ExecutionPlan:
    """Reload a frozen plan and reject any edit to its cases or call ceiling."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid execution plan JSON at {path}: {error}") from error
    if (not isinstance(data, dict) or set(data) != {"version", "variants", "cases", "maxCalls"}
            or data["version"] != PLAN_VERSION or not isinstance(data["cases"], list)):
        raise ValueError(f"Invalid execution plan: expected version {PLAN_VERSION} with complete plan fields.")
    try:
        cases = tuple(get_suite(row["suite"]).parse_row(row["data"]) for row in data["cases"])
        plan = ExecutionPlan(tuple(data["variants"]), cases)
    except (KeyError, TypeError) as error:
        raise ValueError("Invalid execution plan: malformed case record.") from error
    if data != plan.to_dict():
        raise ValueError("Invalid execution plan: cases or model-call limits do not match their frozen fixtures.")
    return plan


def save_plan(path: Path, plan: ExecutionPlan) -> None:
    Path(path).write_text(json.dumps(plan.to_dict(), indent=2) + "\n")


def require_calls(plan: ExecutionPlan | PlanEntry, confirmed: int, *, scope: str = "plan") -> None:
    expected = plan.max_calls if isinstance(plan, ExecutionPlan) else plan.model_calls
    if type(confirmed) is not int or confirmed != expected:
        raise ValueError(f"{scope} requires exactly {expected} confirmed model calls; received {confirmed}.")


def run_id(value: str | None = None) -> str:
    result = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f") if not value else value
    if not isinstance(result, str) or not result.isascii() or not result.isdigit() or not 14 <= len(result) <= 20:
        raise ValueError("Run ID must be a 14–20 digit UTC timestamp.")
    return result


REQUEST_FIELDS = {"source", "model", "variants", "selection", "baseUrl", "capUsd", "capConfirmed", "maxCalls", "runId"}


def validate_request(payload: dict) -> tuple[dict, ExecutionPlan]:
    """Validate the console/worker JSON boundary; return non-secret settings and the plan to freeze."""
    if not isinstance(payload, dict):
        raise ValueError("Settings request must be a JSON object.")
    unknown = set(payload) - REQUEST_FIELDS
    if unknown:
        raise ValueError(f"Unknown settings fields: {', '.join(sorted(unknown))}")
    source = payload.get("source")
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}.")
    model = validate_model(payload.get("model"))
    selection = payload.get("selection", [SELECT_ALL])
    variants = payload.get("variants", [BASE_VARIANT])
    if not isinstance(selection, list) or not isinstance(variants, list):
        raise ValueError("selection and variants must be lists.")
    plan = build_plan(selection, variants)
    if payload.get("maxCalls") is not None:
        require_calls(plan, payload["maxCalls"])
    if source == "openrouter":
        if not is_free_model(model) and payload.get("capConfirmed") is not True:
            raise ValueError("Confirm the active OpenRouter workspace cap before a paid run.")
        cap = None if is_free_model(model) and payload.get("capUsd") is None else validate_cap(payload.get("capUsd"))
    else:
        cap = None
    settings = {"source": source, "model": model, "baseUrl": resolve_base_url(source, payload.get("baseUrl", "")),
                "capUsd": cap, "runId": run_id(payload.get("runId")), "variants": list(plan.variants),
                "selection": selection, "maxCalls": plan.max_calls}
    return settings, plan
