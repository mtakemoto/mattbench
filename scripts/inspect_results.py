"""Rules for reading outcomes and run identity from Inspect logs, shared by scoring and reporting."""

from collections.abc import Iterable, Mapping
from pathlib import PurePath
from typing import Any

PASS_VALUES = ("C", True, 1)
FAIL_VALUES = ("I", False, 0)


def score_passed(value: object) -> bool | None:
    """Map an Inspect score value to pass, fail, or None when it is neither."""
    if value in PASS_VALUES:
        return True
    if value in FAIL_VALUES:
        return False
    return None


def needs_review(metadata: Mapping[str, Any]) -> bool:
    return metadata.get("semantic_review_required") is True or metadata.get("semantic_review_status") == "pending"


def sample_outcome(values: Iterable[object], metadata: Iterable[Mapping[str, Any]]) -> bool | None:
    """True only when every score passed; None when unscored or awaiting human review."""
    values = list(values)
    if not values or any(needs_review(entry) for entry in metadata):
        return None
    return all(score_passed(value) is True for value in values)


def launcher_run_id(relative_log: PurePath) -> str | None:
    """Launchers log to ``<suite>/<run_id>/<file>.eval``; older ad hoc logs have no run ID."""
    parts = relative_log.parts
    candidate = parts[1] if len(parts) > 2 else ""
    return candidate if candidate.isdigit() and 14 <= len(candidate) <= 20 else None
