"""Own a local benchmark from validation through durable report publication."""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.bounded_process import run_bounded
from scripts.execution_plan import describe, validate_request
from scripts.run_inspect_settings import read_env_file


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, allow_nan=False)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def read_job(directory: Path) -> dict | None:
    path = directory / "job.json"
    if not path.exists():
        return None
    job = json.loads(path.read_text())
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
        validated = validate_request(payload)
        settings, plan = validated["settings"], validated["plan"]
        job_id = settings["runId"]
        if (directory / f"{job_id}.plan.json").exists():
            raise ValueError("Run ID already has a frozen plan; choose another run ID.")
        case_id = settings["caseId"]
        entries = (["smoke"] if plan["smokeCases"] else []) + [case["id"] for case in plan["haCases"]]
        timestamp = now()
        job = {"id": job_id, "status": "running", "phase": "validating", "source": settings["source"],
               "model": settings["model"], "variant": settings["variant"], "caseId": case_id,
               "startedAt": timestamp, "updatedAt": timestamp, "completedCases": [], "completedCount": 0,
               "totalCases": len(entries), "message": "Validating frozen execution plan"}
        atomic_json(directory / f"{job_id}.plan.json", plan)
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
        return job
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
    job_id, case_id = settings["runId"], settings["caseId"]
    common = ["--source", settings["source"], "--model", settings["model"], "--run-id", job_id,
              "--plan-file", str(directory / f"{job_id}.plan.json"), "--max-calls", str(settings["maxCalls"])]
    if settings["baseUrl"]:
        common += ["--base-url", settings["baseUrl"]]
    if settings["source"] == "openrouter" and settings["capUsd"] is not None:
        common += ["--cap-usd", str(settings["capUsd"])]
    progress = ["--progress-file", str(directory / f"{job_id}.progress.json")]
    if case_id in ("all", "smart_home", "ha"):
        # Each child has its own bound; the outer budget includes teardown grace per case.
        plan = json.loads((directory / f"{job_id}.plan.json").read_text())
        budget = plan["smokeCalls"] * 125 + 120 + 660 * len(plan["haCases"])
        return [sys.executable, str(ROOT / "scripts/run-inspect-suite.py"), *common, *progress], budget
    if case_id == "smoke":
        return [sys.executable, str(ROOT / "scripts/run-inspect-selected.py"), *common, "--variant", settings["variant"]], settings["maxCalls"] * 125 + 60
    if case_id in ("laptop", "laptop_shopping"):
        return [sys.executable, str(ROOT / "scripts/run-inspect-laptop.py"), *common, *progress], settings["maxCalls"] * 125 + 60
    return [sys.executable, str(ROOT / "scripts/run-inspect-ha-pilot.py"), *common, "--case", case_id, *progress], 600


def merge_progress(directory: Path, job_id: str) -> None:
    path = directory / f"{job_id}.progress.json"
    if not path.exists():
        return
    try:
        progress = json.loads(path.read_text())
        fields = {key: progress[key] for key in ("currentCaseId", "completedCases", "completedCount", "totalCases") if key in progress}
        update_job(directory, job_id, **fields)
    except (ValueError, OSError):
        print("Warning: progress artifact unavailable; retaining durable worker state.", flush=True)


def complete_scores(directory: Path, job_id: str) -> list[dict]:
    job = read_job(directory)
    if not job or job["id"] != job_id:
        raise RuntimeError("Benchmark ownership changed.")
    entries = job["completedCases"]
    summary = ROOT / "artifacts/inspect/summary.json"
    if not summary.exists():
        return entries
    rows = json.loads(summary.read_text())["rows"]
    for entry in entries:
        selected = [row for row in rows if row.get("launcher_run_id") == job_id and
                    (row.get("fixture") == "tasks/smoke.json" if entry["caseId"] == "smoke" else row.get("sample_id") == entry["caseId"])]
        if selected:
            entry["passed"] = (all(row.get("passed") is True for row in selected)
                               if all(row.get("passed") is not None for row in selected) else None)
            entry["modelCalls"] = sum(row.get("model_calls", 0) for row in selected)
    return entries


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
        result = run_bounded(args, timeout=budget, cwd=ROOT, terminate_grace=60)
        merge_progress(directory, job_id)
        if settings["caseId"] != "all":
            update_job(directory, job_id, completedCases=[{"caseId": settings["caseId"], "status": "complete" if result.returncode == 0 else "failed"}], completedCount=1)
        billing_ok = True
        if settings["source"] == "openrouter":
            update_job(directory, job_id, phase="billing", message="Reading billed OpenRouter cost")
            try:
                billing = run_bounded([sys.executable, str(ROOT / "scripts/openrouter-billing.py"), "--run-id", job_id], timeout=120, cwd=ROOT)
                billing_ok = billing.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                billing_ok = False
        update_job(directory, job_id, phase="exporting", message="Publishing Inspect results")
        export = run_bounded([sys.executable, str(ROOT / "scripts/inspect-report.py")], timeout=180, cwd=ROOT)
        ok = result.returncode == 0 and export.returncode == 0
        warning = ""
        if export.returncode == 0:
            summary = json.loads((ROOT / "artifacts/inspect/summary.json").read_text())
            if summary.get("warnings"):
                warning = " Report is incomplete; inspect artifact warnings."
        update_job(directory, job_id, completedCases=complete_scores(directory, job_id), status="complete" if ok else "failed",
                   phase="complete" if ok else "failed", finishedAt=now(), pid=None,
                   message=(("Run and export complete." if billing_ok else "Run complete; billed cost is incomplete.") if ok else
                            "Run or export failed; see the ignored local run log.") + warning)
        return 0 if ok else 1
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        merge_progress(directory, job_id)
        update_job(directory, job_id, status="interrupted", phase="interrupted", finishedAt=now(), pid=None,
                   message="Worker interrupted or exceeded its deadline; owned child cleanup was attempted.")
        return 1
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
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--work")
    parser.add_argument("--lock-fd", type=int)
    parser.add_argument("--ready-fd", type=int)
    args = parser.parse_args()
    if args.work:
        return work(args.work, args.directory, args.lock_fd, args.ready_fd)
    try:
        if args.start:
            result = start_job(json.load(sys.stdin), args.directory)
        elif args.describe:
            result = describe()
        elif args.status:
            result = reconcile(args.directory)
        else:
            parser.error("Choose --start, --status or --describe.")
        print(json.dumps(result, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        # Shared validators contain controlled diagnostics, never response bodies or credentials.
        print(json.dumps({"error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
