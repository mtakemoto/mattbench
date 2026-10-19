"""Run a frozen suite with a confirmed total generation ceiling."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai.log import read_eval_log
from scripts.bounded_process import run_bounded
from scripts.execution_plan import ExecutionPlan, build_plan, load_plan, require_calls, run_id, save_plan
from scripts.run_inspect_settings import prepare_provider


def case_score(kind: str, case_id: str, identifier: str, expected_ids: tuple[str, ...]) -> tuple[bool | None, int | None, str | None]:
    """A corrupt or incomplete log is unavailable, never a fabricated score."""
    directory = ROOT / "artifacts/inspect" / ("selected" if kind == "smoke" else "laptops" if kind == "laptop" else "ha") / identifier
    samples = []
    try:
        paths = sorted(directory.glob("*.eval"))
        if not paths:
            return None, None, "Score unavailable: Inspect log is missing."
        for path in paths:
            samples.extend(sample for sample in (read_eval_log(path).samples or [])
                           if kind == "smoke" or sample.id == case_id)
        wanted = Counter(sample_id.split(":", 1)[1] for sample_id in expected_ids) if kind == "smoke" else Counter([case_id])
        if Counter(sample.id for sample in samples) != wanted:
            return None, None, "Score unavailable: Inspect sample IDs do not match the frozen plan."
        if any(not sample.scores for sample in samples):
            return None, None, "Score unavailable: an Inspect sample has no score."
        values = [score.value for sample in samples for score in sample.scores.values()]
        calls = sum(event.event == "model" for sample in samples for event in (sample.events or []))
        return all(value in ("C", True, 1) for value in values), calls, None
    except Exception as error:
        return None, None, f"Score unavailable: could not read Inspect artifact ({type(error).__name__})."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("freetoken", "openrouter", "compatible"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--progress-file", required=True)
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--plan-file", type=Path)
    args = parser.parse_args()
    try:
        identifier = run_id(args.run_id)
        prepare_provider(args.source, args.model, base_url=args.base_url, cap_usd=args.cap_usd, discover=False)
        plan = load_plan(args.plan_file) if args.plan_file else build_plan(suite=True)
        if plan.variants != ("base",) or not plan.smoke_cases or not plan.ha_cases:
            raise ValueError("Suite requires base smoke rows and at least one HA case.")
        require_calls(plan, args.max_calls, scope="Suite")
    except (ValueError, OSError) as error:
        parser.error(str(error))

    if args.plan_file is None:
        frozen_path = ROOT / "artifacts/inspect/plans" / f"{identifier}.json"
        frozen_path.parent.mkdir(parents=True, exist_ok=True)
        if frozen_path.exists():
            parser.error("Run ID already has a frozen plan; choose another run ID.")
        save_plan(frozen_path, plan)
    else:
        frozen_path = args.plan_file
    smoke_path = frozen_path.parent / f"{identifier}-smoke.json"
    if plan.smoke_cases:
        save_plan(smoke_path, ExecutionPlan(plan.variants, plan.smoke_cases, ()))
    entries = []
    if plan.smoke_cases:
        entries.append(("smoke", "Pinned smoke set", "smoke"))
    if plan.ha_cases:
        entries.extend((case.id, case.name, "ha") for case in plan.ha_cases)
    if plan.laptop_cases:
        entries.append(("laptop", "Laptop shopping evaluation", "laptop"))
    completed = []

    def update(phase: str, current: str | None, message: str) -> None:
        data = {"phase": phase, "currentCaseId": current, "completedCases": completed,
                "completedCount": len(completed), "totalCases": len(entries), "message": message,
                "updatedAt": datetime.now(timezone.utc).isoformat()}
        destination = Path(args.progress_file)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(data) + "\n")
        temporary.replace(destination)

    failures = 0
    update("preparing", None, "Preparing frozen suite")
    for case_id, name, kind in entries:
        update("running", case_id, f"Running {name}")
        if kind == "smoke":
            command = [sys.executable, str(ROOT / "scripts/run-inspect-selected.py"), "--source", args.source,
                       "--model", args.model, "--variant", "base", "--max-calls", str(plan.smoke_calls),
                       "--plan-file", str(smoke_path), "--run-id", identifier]
            timeout = plan.smoke_calls * 125 + 60
        elif kind == "laptop":
            command = [sys.executable, str(ROOT / "scripts/run-inspect-laptop.py"),
                       "--source", args.source, "--model", args.model, "--run-id", identifier,
                       "--max-calls", str(plan.laptop_calls), "--plan-file", str(frozen_path),
                       "--progress-file", args.progress_file]
            timeout = plan.laptop_calls * 125 + 60
        else:
            case = plan.ha_case(case_id)
            command = [sys.executable, str(ROOT / "scripts/run-inspect-ha-pilot.py"), "--case", case_id,
                       "--source", args.source, "--model", args.model, "--run-id", identifier,
                       "--max-calls", str(case["max_model_calls"]), "--plan-file", str(frozen_path),
                       "--progress-file", args.progress_file]
            timeout = 600
        if args.base_url:
            command.extend(["--base-url", args.base_url])
        if args.source == "openrouter" and args.cap_usd is not None:
            command.extend(["--cap-usd", str(args.cap_usd)])
        try:
            return_code = run_bounded(command, cwd=ROOT, check=False, timeout=timeout, terminate_grace=60).returncode
            message = None if return_code == 0 else f"{name} could not complete (exit status {return_code})."
        except subprocess.TimeoutExpired:
            return_code = 124
            message = f"{name} timed out; child process group terminated."
        except OSError as error:
            return_code = 127
            message = f"{name} could not start ({type(error).__name__})."
        state = "complete" if return_code == 0 else "failed"
        if state == "failed":
            failures += 1
        item = {"caseId": case_id, "status": state, "message": message}
        if state == "complete":
            passed, calls, diagnostic = case_score(kind, case_id, identifier, plan.sample_ids)
            if diagnostic:
                item["scoreUnavailable"] = diagnostic
                item["message"] = diagnostic
            else:
                item.update({"passed": passed, "modelCalls": calls})
        completed.append(item)
        update("running", None if len(completed) == len(entries) else entries[len(completed)][0],
               f"{len(completed)} of {len(entries)} cases finished")
    update("exporting", None, "Exporting Inspect results")
    return 1 if failures else 0


def interrupt_worker(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt_worker)
    raise SystemExit(main())
