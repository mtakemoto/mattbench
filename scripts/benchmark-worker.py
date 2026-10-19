"""Own a local benchmark from validation through durable report publication."""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.bounded_process import run_bounded
from scripts.case_progress import FINISHED_STATES, case_key, read_case_records
from scripts.execution_plan import load_plan, validate_request
from scripts.json_files import write_json_atomic
from scripts.run_inspect_settings import read_env_file
from suites import RunTarget


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict) -> None:
    write_json_atomic(path, value, allow_nan=False)


PROGRESS_FIELDS = ("currentEntryId", "completedEntries", "totalEntries", "message")
"""Orchestrator fields that refine a running job; billing, export and identity stay worker-owned."""


def upgrade_legacy_job(job: dict) -> dict:
    """Jobs written before suite discovery stored one selection, one variant and 'case' counters for entries."""
    if "caseId" in job:
        job["selection"] = [job.pop("caseId")]
        variant = job.pop("variant", "base")
        job["variants"] = ["base", "careful"] if variant == "both" else [variant]
    if "totalCases" in job:
        job["totalEntries"] = job.pop("totalCases")
        job["completedEntries"] = [{**{k: v for k, v in entry.items() if k != "caseId"}, "entryId": entry.get("caseId")}
                                   for entry in job.pop("completedCases", [])]
        job["currentEntryId"] = job.pop("currentCaseId", None)
        job.pop("completedCount", None)
    return job


def read_job(directory: Path) -> dict | None:
    path = directory / "job.json"
    if not path.exists():
        return None
    job = json.loads(path.read_text())
    if isinstance(job, dict):
        job = upgrade_legacy_job(job)
    if not isinstance(job, dict) or not isinstance(job.get("id"), str) or job.get("status") not in {"running", "complete", "failed", "interrupted"}:
        raise ValueError("Invalid persisted benchmark job.")
    return job


def update_job(directory: Path, job_id: str, **updates) -> dict:
    job = read_job(directory)
    if not job or job["id"] != job_id:
        raise RuntimeError("Benchmark job ownership changed; refusing stale update.")
    job.update(updates, updatedAt=now())
    atomic_json(directory / "job.json", job)
    return job


def acquire_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory / "run.lock").open("a+")
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        raise ValueError("A benchmark is already running.") from None
    return stream


def reconcile(directory: Path) -> dict | None:
    try:
        lock = acquire_lock(directory)
    except ValueError:
        return read_job(directory)
    try:
        job = read_job(directory)
        if job and job["status"] == "running":
            return update_job(directory, job["id"], status="interrupted", phase="interrupted", finishedAt=now(),
                              message="Worker stopped before the run completed.", pid=None)
        return job
    finally:
        lock.close()


def start_job(payload: dict, directory: Path) -> dict:
    # One OS lock owns both startup and the inherited worker lifecycle.
    lock = acquire_lock(directory)
    ready_read = ready_write = None
    child = None
    job = None
    try:
        if not isinstance(payload, dict) or type(payload.get("maxCalls")) is not int:
            raise ValueError("Confirm an integer maxCalls ceiling before starting a benchmark.")
        settings, plan = validate_request(payload)
        job_id = settings["runId"]
        if (directory / f"{job_id}.plan.json").exists():
            raise ValueError("Run ID already has a frozen plan; choose another run ID.")
        timestamp = now()
        job = {"id": job_id, "status": "running", "phase": "validating", "source": settings["source"],
               "model": settings["model"], "variants": settings["variants"], "selection": settings["selection"],
               "startedAt": timestamp, "updatedAt": timestamp, "completedEntries": [],
               "totalEntries": len(plan.entries), "message": "Validating frozen execution plan"}
        atomic_json(directory / f"{job_id}.plan.json", plan.to_dict())
        atomic_json(directory / f"{job_id}.request.json", settings)
        atomic_json(directory / "job.json", job)
        ready_read, ready_write = os.pipe()
        environment = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
        # Credentials travel only in the selected worker's environment, never persisted job/request files.
        if settings["source"] == "openrouter":
            key = os.environ.get("OPENROUTER_API_KEY") or read_env_file().get("OPENROUTER_API_KEY")
            if not key:
                raise ValueError("OPENROUTER_API_KEY is missing.")
            environment["OPENROUTER_API_KEY"] = key
        with (directory / f"{job_id}.log").open("a") as output:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--work", job_id,
                                      "--directory", str(directory), "--lock-fd", str(lock.fileno()),
                                      "--ready-fd", str(ready_read)], cwd=ROOT, env=environment,
                                     stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                     pass_fds=(lock.fileno(), ready_read), start_new_session=True)
        job = update_job(directory, job_id, pid=child.pid)
        os.write(ready_write, b"1")
        return {**job, "cases": job_cases(directory, job)}
    except BaseException:
        if child:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        if job:
            update_job(directory, job["id"], status="failed", phase="failed", finishedAt=now(),
                       message="Could not start benchmark worker.", pid=None)
        raise
    finally:
        for descriptor in (ready_read, ready_write):
            if descriptor is not None:
                os.close(descriptor)
        lock.close()


def command(settings: dict, directory: Path) -> tuple[list[str], float]:
    """Suite orchestrator command for a frozen run, and its whole-run deadline in seconds."""
    job_id = settings["runId"]
    plan_file = directory / f"{job_id}.plan.json"
    target = RunTarget(settings["source"], settings["model"], job_id, plan_file,
                       settings["baseUrl"], settings["capUsd"], directory / f"{job_id}.progress.json")
    arguments = [*target.arguments(), "--max-calls", str(settings["maxCalls"]),
                 "--progress-file", str(target.progress_file)]
    return [sys.executable, str(ROOT / "scripts/run-inspect-suite.py"), *arguments], load_plan(plan_file).deadline_seconds


def read_progress(directory: Path, job_id: str) -> dict:
    try:
        progress = json.loads((directory / f"{job_id}.progress.json").read_text())
    except (OSError, ValueError):
        return {}
    return {key: progress[key] for key in PROGRESS_FIELDS if isinstance(progress, dict) and key in progress}


def merge_progress(directory: Path, job_id: str) -> None:
    fields = read_progress(directory, job_id)
    if fields:
        update_job(directory, job_id, **fields)


def job_cases(directory: Path, job: dict) -> list[dict]:
    """Every case of the frozen plan with its live state: queued, running, pass, fail, unscored, error or not_run."""
    try:
        plan = load_plan(directory / f"{job['id']}.plan.json")
    except ValueError:
        return []
    records = read_case_records(directory, job["id"])
    failed_entries = {entry.get("entryId") for entry in job.get("completedEntries", []) if entry.get("status") == "failed"}
    cases = []
    for entry in plan.entries:
        for variant in plan.variants:
            for case in entry.cases:
                record = records.get(case_key(variant, case.id), {})
                state = record.get("state", "queued")
                if state not in FINISHED_STATES:
                    state = "error" if entry.id in failed_entries else state if job["status"] == "running" else "not_run"
                cases.append({"id": case.id, "suite": case.suite, "variant": variant, "state": state,
                              **{key: record[key] for key in ("truncated", "calls", "explanation") if key in record}})
    return cases


def status(directory: Path) -> dict | None:
    """The job as the console shows it: live orchestrator progress and per-case states merged in."""
    job = reconcile(directory)
    if not job:
        return None
    if job["status"] == "running" and job["phase"] in ("validating", "running"):
        job.update(read_progress(directory, job["id"]))
    job["cases"] = job_cases(directory, job)
    return job


def cancel(directory: Path) -> dict | None:
    """Ask the running worker to stop; it keeps finished cases and still publishes billing and results."""
    job = read_job(directory)
    if not job or job["status"] != "running":
        raise ValueError("No benchmark is running.")
    try:
        lock = acquire_lock(directory)
    except ValueError:
        pass  # The worker is alive: it holds the lock for its whole lifecycle.
    else:
        lock.close()
        return status(directory)
    (directory / f"{job['id']}.cancel").touch()
    if job.get("pid"):
        os.killpg(job["pid"], signal.SIGTERM)
    return status(directory)


def collect_billing(directory: Path, job_id: str) -> bool:
    update_job(directory, job_id, phase="billing", message="Reading billed OpenRouter cost")
    try:
        result = run_bounded([sys.executable, str(ROOT / "scripts/openrouter-billing.py"), "--run-id", job_id], timeout=120, cwd=ROOT)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def export_results(directory: Path, job_id: str) -> tuple[bool, bool]:
    """Publish the summary; returns (exported, summary has warnings)."""
    update_job(directory, job_id, phase="exporting", message="Publishing Inspect results")
    if run_bounded([sys.executable, str(ROOT / "scripts/inspect-report.py")], timeout=180, cwd=ROOT).returncode:
        return False, False
    return True, bool(json.loads((ROOT / "artifacts/inspect/summary.json").read_text()).get("warnings"))


def work(job_id: str, directory: Path, lock_fd: int, ready_fd: int) -> int:
    # The launch handshake fences the initial PID publication.
    try:
        if os.read(ready_fd, 1) != b"1":
            raise RuntimeError("Worker launch was interrupted.")
    finally:
        os.close(ready_fd)
    settings = json.loads((directory / f"{job_id}.request.json").read_text())

    def interrupt(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    try:
        args, budget = command(settings, directory)
        update_job(directory, job_id, phase="running", message="Running frozen benchmark selection")
        stopped = None
        try:
            evaluated = run_bounded(args, timeout=budget, cwd=ROOT, terminate_grace=60).returncode == 0
        except (KeyboardInterrupt, subprocess.TimeoutExpired) as error:
            evaluated = False
            cancelled = isinstance(error, KeyboardInterrupt) and (directory / f"{job_id}.cancel").exists()
            stopped = "Run cancelled; finished cases were kept." if cancelled else \
                "Worker interrupted or exceeded its deadline; owned child cleanup was attempted."
        # Billing and export are short and bounded; finish them so paid calls and finished cases are recorded.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        merge_progress(directory, job_id)
        billed = collect_billing(directory, job_id) if settings["source"] == "openrouter" else True
        exported, has_warnings = export_results(directory, job_id)
        ok = evaluated and exported
        if stopped:
            final, message = "interrupted", stopped
        elif ok:
            final, message = "complete", "Run and export complete." if billed else "Run complete; billed cost is incomplete."
        else:
            final, message = "failed", "Run or export failed; see the ignored local run log."
        if has_warnings:
            message += " Some report artifacts have warnings."
        update_job(directory, job_id, status=final, phase=final, finishedAt=now(), pid=None, message=message)
        return 0 if ok else 1
    except Exception:
        update_job(directory, job_id, status="failed", phase="failed", finishedAt=now(), pid=None,
                   message="Benchmark worker failed; see the ignored local run log.")
        raise
    finally:
        os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "artifacts/web")
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--cancel", action="store_true")
    parser.add_argument("--work")
    parser.add_argument("--lock-fd", type=int)
    parser.add_argument("--ready-fd", type=int)
    args = parser.parse_args()
    if args.work:
        return work(args.work, args.directory, args.lock_fd, args.ready_fd)
    try:
        if args.start:
            result = start_job(json.load(sys.stdin), args.directory)
        elif args.status:
            result = status(args.directory)
        elif args.cancel:
            result = cancel(args.directory)
        else:
            parser.error("Choose --start, --status or --cancel.")
        print(json.dumps(result, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        # Shared validators contain controlled diagnostics, never response bodies or credentials.
        print(json.dumps({"error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
