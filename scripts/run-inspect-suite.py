"""Run every entry of a frozen plan in order, publishing progress and per-entry outcomes.

A failed entry is recorded and later entries still run; the exit status is
nonzero when any entry failed.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai.log import read_eval_log
from scripts.bounded_process import run_bounded
from scripts.execution_plan import CHILD_TERMINATE_GRACE_SECONDS, PlanEntry, load_plan, require_calls, run_id
from scripts.inspect_results import sample_outcome
from scripts.json_files import write_json_atomic
from scripts.run_inspect_settings import SOURCES, prepare_provider
from suites import RunTarget


def entry_score(entry: PlanEntry, identifier: str) -> tuple[bool | None, int | None, str | None]:
    """Score one entry from its Inspect logs; a corrupt or incomplete log is unavailable, never guessed."""
    try:
        paths = sorted(entry.suite.log_dir(identifier).glob("*.eval"))
        if not paths:
            return None, None, "Score unavailable: Inspect log is missing."
        wanted = entry.expected_samples
        samples = [sample for path in paths for sample in (read_eval_log(path).samples or []) if sample.id in wanted]
        if sorted(sample.id for sample in samples) != sorted(wanted.elements()):
            return None, None, "Score unavailable: Inspect sample IDs do not match the frozen plan."
        if any(not sample.scores for sample in samples):
            return None, None, "Score unavailable: an Inspect sample has no score."
        scores = [score for sample in samples for score in sample.scores.values()]
        passed = sample_outcome((score.value for score in scores), (score.metadata or {} for score in scores))
        calls = sum(event.event == "model" for sample in samples for event in (sample.events or []))
        return passed, calls, None
    except Exception as error:
        return None, None, f"Score unavailable: could not read Inspect artifact ({type(error).__name__})."


def run_entry(entry: PlanEntry, target: RunTarget, identifier: str) -> dict:
    """Run one child process and return its completed-case record."""
    try:
        return_code = run_bounded(entry.command(target), cwd=ROOT, check=False, timeout=entry.timeout_seconds,
                                  terminate_grace=CHILD_TERMINATE_GRACE_SECONDS).returncode
        message = None if return_code == 0 else f"{entry.label} could not complete (exit status {return_code})."
    except subprocess.TimeoutExpired:
        message = f"{entry.label} timed out; child process group terminated."
    except OSError as error:
        message = f"{entry.label} could not start ({type(error).__name__})."
    if message:
        return {"caseId": entry.id, "status": "failed", "message": message}
    passed, calls, unavailable = entry_score(entry, identifier)
    if unavailable:
        return {"caseId": entry.id, "status": "complete", "message": unavailable, "scoreUnavailable": unavailable}
    return {"caseId": entry.id, "status": "complete", "message": None, "passed": passed, "modelCalls": calls}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--progress-file", type=Path, required=True)
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--plan-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        identifier = run_id(args.run_id)
        prepare_provider(args.source, args.model, base_url=args.base_url, cap_usd=args.cap_usd, discover=False)
        plan = load_plan(args.plan_file)
        require_calls(plan, args.max_calls, scope="Run")
    except (ValueError, OSError) as error:
        parser.error(str(error))

    target = RunTarget(args.source, args.model, identifier, args.plan_file, args.base_url, args.cap_usd,
                       args.progress_file)
    entries = plan.entries
    completed: list[dict] = []

    def publish(phase: str, current: str | None, message: str) -> None:
        write_json_atomic(args.progress_file, {
            "phase": phase, "currentCaseId": current, "completedCases": completed,
            "completedCount": len(completed), "totalCases": len(entries), "message": message,
            "updatedAt": datetime.now(timezone.utc).isoformat()})

    publish("preparing", None, "Preparing frozen plan")
    for index, entry in enumerate(entries):
        publish("running", entry.id, f"Running {entry.label}")
        completed.append(run_entry(entry, target, identifier))
        following = entries[index + 1].id if index + 1 < len(entries) else None
        publish("running", following, f"{len(completed)} of {len(entries)} cases finished")
    publish("exporting", None, "Exporting Inspect results")
    return 1 if any(item["status"] == "failed" for item in completed) else 0


def interrupt_worker(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt_worker)
    raise SystemExit(main())
