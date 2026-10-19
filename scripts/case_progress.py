"""Per-case live progress, published by an Inspect hook and merged into the job status.

The suite orchestrator gives each child process its own file through
``CASE_PROGRESS_ENV``; importing this module registers a hook that records
each sample's start and outcome there. Sample IDs are case IDs, so the
records apply to every suite without suite-specific code.
"""

from __future__ import annotations

import json
import os
from functools import cache
from pathlib import Path
from typing import Any

from inspect_ai.hooks import Hooks, SampleEnd, SampleStart, hooks

from scripts.inspect_results import sample_outcome
from scripts.json_files import write_json_atomic

CASE_PROGRESS_ENV = "MATTBENCH_CASE_PROGRESS_FILE"
FINISHED_STATES = {"pass", "fail", "unscored", "error"}


def case_key(variant: str, case_id: str) -> str:
    """One case under one prompt variant; a compare run evaluates each case once per variant."""
    return f"{variant}/{case_id}"


def case_progress_file(progress_file: Path, entry_id: str) -> Path:
    return progress_file.with_name(f"{progress_file.name.removesuffix('.progress.json')}.cases.{entry_id}.json")


def read_case_records(directory: Path, run_id: str) -> dict[str, dict[str, Any]]:
    """Merge every entry's records for one run; a damaged file is skipped, never fatal."""
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob(f"{run_id}.cases.*.json")):
        try:
            content = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(content, dict):
            records.update({key: value for key, value in content.items() if isinstance(value, dict)})
    return records


def _record(key: str, **fields: Any) -> None:
    path = Path(os.environ[CASE_PROGRESS_ENV])
    try:
        current = json.loads(path.read_text())
    except (OSError, ValueError):
        current = {}
    current[key] = fields
    write_json_atomic(path, current)


def _variant(metadata: dict | None) -> str:
    return (metadata or {}).get("prompt_variant", "base")


class CaseProgressHooks(Hooks):
    def enabled(self) -> bool:
        return bool(os.environ.get(CASE_PROGRESS_ENV))

    async def on_sample_start(self, data: SampleStart) -> None:
        _record(case_key(_variant(data.summary.metadata), str(data.summary.id)), state="running")

    async def on_sample_end(self, data: SampleEnd) -> None:
        sample = data.sample
        scores = list((sample.scores or {}).values())
        passed = sample_outcome((score.value for score in scores), (score.metadata or {} for score in scores))
        state = "error" if sample.error else "unscored" if passed is None else "pass" if passed else "fail"
        explanation = next((score.explanation for score in scores if score.explanation), None)
        _record(case_key(_variant(sample.metadata), str(sample.id)), state=state,
                truncated=getattr(sample.output, "stop_reason", None) == "max_tokens",
                calls=sum(event.event == "model" for event in sample.events or []), explanation=explanation)


@cache
def install() -> None:
    """Register the hook in this process; Inspect calls it only when the orchestrator set a file."""
    hooks(name="mattbench_case_progress", description="Publish each case's start and outcome for the live console.")(CaseProgressHooks)
