"""Run one Inspect case against real ha-mcp and a disposable Synthetic Home.

Requires Docker and a local/private OpenAI-compatible model for scored runs.
Preflight needs no model. The first run fetches pinned public Synthetic Home
source, then reuses an ignored local cache. No production HA URL or token.
"""

import asyncio
import argparse
from contextlib import contextmanager
import inspect
import json
import os
import secrets
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

import aiohttp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inspect_ai import eval as run_eval
from inspect_pilot import HA_STATE_READER, ha_matches
from scripts.bounded_process import run_bounded
from scripts.execution_plan import build_plan, load_plan, require_calls, run_id as run_id_value
from scripts.json_files import write_json_atomic
from scripts.run_inspect_settings import GENERATION, SOURCES, prepare_provider
from suites.smart_home import SUITE

SYNTHETIC_SHA = "3a943b1346cad6c4d41f9c148921f87c9229bb0b"
HA_IMAGE = "mattbench-synthetic-ha:2026.10.1-v1"
MCP_IMAGE = "ghcr.io/homeassistant-ai/ha-mcp@sha256:f0a08038a230bd80a55332a1db1a955df48df018cfcc508c37c7f462c564c668"


SETUP_TIMEOUT = 240
EVALUATION_TIMEOUT = 180
TEARDOWN_TIMEOUT = 40
DOCKER_TIMEOUT = 20


class WorkerInterrupted(RuntimeError):
    """The supervising worker requested shutdown."""


@contextmanager
def deadline(seconds: float, phase: str):
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum, _frame):
        raise TimeoutError(f"{phase} exceeded its {seconds:g}s deadline")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def docker(*args: str, timeout: float = DOCKER_TIMEOUT) -> str:
    completed = run_bounded(["docker", *args], timeout=timeout, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"Docker command {args[0]} failed (exit {completed.returncode}).")
    return completed.stdout.strip()


def install_synthetic_component(config: Path) -> None:
    archive_url = f"https://github.com/allenporter/home-assistant-synthetic-home/archive/{SYNTHETIC_SHA}.tar.gz"
    cache = ROOT / "artifacts/inspect/cache" / f"synthetic-home-{SYNTHETIC_SHA}.tar.gz"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        with urlopen(archive_url, timeout=60) as response:
            data = response.read()
        temporary = cache.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(cache)
    archive = tarfile.open(cache, mode="r:gz")
    destination = config / "custom_components" / "synthetic_home"
    destination.mkdir(parents=True)
    prefix = f"home-assistant-synthetic-home-{SYNTHETIC_SHA}/custom_components/synthetic_home/"
    for member in archive.getmembers():
        if not member.isfile() or not member.name.startswith(prefix):
            continue
        relative = Path(member.name.removeprefix(prefix))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Unsafe upstream archive path")
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        with archive.extractfile(member) as source, output.open("wb") as target:
            shutil.copyfileobj(source, target)
    if not (destination / "manifest.json").exists():
        raise RuntimeError("Pinned Synthetic Home integration is incomplete")


def docker_python(container: str, source: str, data: str = "", *, timeout: float = DOCKER_TIMEOUT) -> str:
    completed = run_bounded(
        ["docker", "exec", "-i", container, "python", "-c", source],
        timeout=timeout, input=data, capture_output=True,
    )
    if completed.returncode:
        # Do not echo Docker stderr: it can contain credentials or private responses.
        raise RuntimeError(f"Python in disposable container failed (exit {completed.returncode}).")
    return completed.stdout.strip()


def wait_http(container: str, timeout: int = 150) -> None:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        try:
            docker_python(container, "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8123/api/onboarding', timeout=2)",
                          timeout=min(8, max(0.1, until - time.monotonic())))
            return
        except (RuntimeError, subprocess.TimeoutExpired):
            time.sleep(min(2, max(0, until - time.monotonic())))
    raise RuntimeError("Synthetic Home Assistant did not start")


async def bootstrap(ha_url: str, password: str, fixture_name: str) -> str:
    client_id = "http://127.0.0.1/"
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{ha_url}/api/onboarding") as response:
            steps = await response.json()
        if not any(step["step"] == "user" and not step["done"] for step in steps):
            raise RuntimeError("Disposable HA config was already onboarded")
        async with session.post(f"{ha_url}/api/onboarding/users", json={
            "client_id": client_id,
            "name": "Synthetic Benchmark",
            "username": "synthetic_benchmark",
            "password": password,
            "language": "en",
        }) as response:
            response.raise_for_status()
            auth_code = (await response.json())["auth_code"]
        async with session.post(f"{ha_url}/auth/token", data={
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": auth_code,
        }) as response:
            response.raise_for_status()
            access_token = (await response.json())["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.post(f"{ha_url}/api/config/config_entries/flow", headers=headers,
                                json={"handler": "synthetic_home"}) as response:
            response.raise_for_status()
            flow = await response.json()
        if flow.get("type") != "form":
            raise RuntimeError("Synthetic Home config flow did not present a form")
        async with session.post(f"{ha_url}/api/config/config_entries/flow/{flow['flow_id']}",
                                headers=headers, json={"config_filename": fixture_name}) as response:
            response.raise_for_status()
            result = await response.json()
        if result.get("type") != "create_entry":
            raise RuntimeError("Synthetic Home config flow did not create an entry")
        return access_token


def state(container: str, token: str, entity_id: str) -> dict:
    return json.loads(docker_python(container, HA_STATE_READER, json.dumps({"entity": entity_id, "token": token})))


async def apply_preflight_action(container: str, action: dict, entities: list[str]) -> None:
    """Exercise the same real ha-mcp stdio and service path used by Inspect."""
    params = StdioServerParameters(command="docker", args=["exec", "-i", container, "ha-mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {tool.name for tool in (await session.list_tools()).tools}
            if not {"ha_call_service", "ha_get_state"} <= tools:
                raise RuntimeError("Pinned ha-mcp image is missing required tools")
            data = dict(action["data"])
            entity_id = data.pop("entity_id")
            result = await session.call_tool("ha_call_service", {
                "domain": action["domain"], "service": action["service"],
                "entity_id": entity_id, "data": json.dumps(data),
            })
            if result.is_error:
                raise RuntimeError("Synthetic ha-mcp service call failed")
            for entity in entities:
                readback = await session.call_tool("ha_get_state", {"entity_id": entity})
                if readback.is_error:
                    raise RuntimeError("Synthetic ha-mcp state read failed")


def progress(path: str, case_id: str, message: str, phase: str = "running") -> None:
    if not path:
        return
    destination = Path(path)
    current = {}
    try:
        current = json.loads(destination.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    current.update({"phase": phase, "currentCaseId": case_id, "message": message,
                    "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    write_json_atomic(destination, current)

def best_effort_progress(path: str, case_id: str, message: str) -> None:
    try:
        progress(path, case_id, message)
    except Exception as error:
        print(f"Progress publication failed during teardown ({type(error).__name__}).",
              file=sys.stderr, flush=True)


def cleanup_resources(mcp_container: str, ha_container: str, network: str) -> list[str]:
    """Clean independently: a failed chown/remove cannot skip any owned resource."""
    operations = (
        ("Restore HA config ownership", ["docker", "exec", "-u", "0", ha_container,
                                         "chown", "-R", f"{os.getuid()}:{os.getgid()}", "/config"]),
        ("Remove MCP container", ["docker", "rm", "-f", mcp_container]),
        ("Remove HA container", ["docker", "rm", "-f", ha_container]),
        ("Remove isolated network", ["docker", "network", "rm", network]),
    )
    until = time.monotonic() + TEARDOWN_TIMEOUT
    diagnostics = []
    for label, command in operations:
        try:
            result = run_bounded(command, timeout=min(8, max(0.1, until - time.monotonic())),
                                 capture_output=True)
            stderr = result.stderr.lower()
            missing = any(reason in stderr for reason in ("no such container", "no such network"))
            if result.returncode and not missing:
                diagnostics.append(f"{label}: exit {result.returncode}")
        except Exception as error:
            diagnostics.append(f"{label}: {type(error).__name__}")
    return diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="mxz_coordinator_target")
    parser.add_argument("--source", choices=SOURCES, default="freetoken")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--plan-file")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--progress-file", default="")
    parser.add_argument("--preflight-only", action="store_true", help="Verify fixture and service path without a model")
    args = parser.parse_args()
    try:
        plan = load_plan(Path(args.plan_file)) if args.plan_file else build_plan([args.case])
        run_id = run_id_value(args.run_id or None)
        entry = plan.entry(SUITE.id, [args.case])
        case = entry.cases[0].data
        if args.max_calls is not None:
            require_calls(entry, args.max_calls, scope="HA case")
        if not args.preflight_only and not args.plan_file and args.max_calls is None:
            raise ValueError("A frozen execution plan or confirmed --max-calls is required.")
        if not args.preflight_only:
            if not args.model:
                parser.error("Model is required for a benchmark run.")
            model_name = prepare_provider(args.source, args.model, base_url=args.base_url or "",
                                          cap_usd=args.cap_usd)
    except ValueError as error:
        parser.error(str(error))

    clock_start = time.monotonic()
    setup_done: float | None = None
    eval_done: float | None = None
    log_ids: list[str] = []
    outcome = "failed"
    failed = False
    interrupted = False
    cleaning = False
    suffix = secrets.token_hex(5)
    network = f"mattbench-ha-{suffix}"
    ha_container = f"mattbench-ha-{suffix}"
    mcp_container = f"mattbench-mcp-{suffix}"
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def interrupt(_signum, _frame):
        nonlocal interrupted
        interrupted = True
        if not cleaning:
            raise WorkerInterrupted("Worker interrupted; cleaning up disposable resources.")

    signal.signal(signal.SIGTERM, interrupt)
    try:
        with tempfile.TemporaryDirectory(prefix="mattbench-ha-", ignore_cleanup_errors=True) as temp:
            try:
                with deadline(SETUP_TIMEOUT, "HA setup"):
                    progress(args.progress_file, args.case, "Preparing fictional fixture and isolated Home Assistant", "preparing")
                    config = Path(temp) / "config"
                    config.mkdir()
                    (config / "configuration.yaml").write_text("default_config:\nhomeassistant:\n  unit_system: imperial\n")
                    fixture = ROOT / case["fixture"]
                    if not fixture.is_file() or fixture.parent != ROOT / "fixtures/ha":
                        raise RuntimeError("Case fixture must be a pinned file in fixtures/ha")
                    shutil.copy2(fixture, config / fixture.name)
                    install_synthetic_component(config)
                    progress(args.progress_file, args.case, "Starting disposable Home Assistant")
                    docker("network", "create", "--internal", network)
                    docker("run", "-d", "--name", ha_container, "--network", network,
                           "--mount", f"type=bind,src={config},dst=/config",
                           "--env", "TZ=UTC", HA_IMAGE)
                    wait_http(ha_container)
                    bootstrap_source = "import asyncio, aiohttp\n" + inspect.getsource(bootstrap)
                    bootstrap_source += f"\nimport sys\nprint(asyncio.run(bootstrap('http://127.0.0.1:8123', sys.stdin.read().strip(), {fixture.name!r})))\n"
                    token = docker_python(ha_container, bootstrap_source, secrets.token_urlsafe(24))
                    until = time.monotonic() + 30
                    while time.monotonic() < until:
                        try:
                            actual = {entity: state(ha_container, token, entity) for entity in case["initial"]}
                            break
                        except (RuntimeError, subprocess.TimeoutExpired, ValueError):
                            time.sleep(1)
                    else:
                        raise RuntimeError("Synthetic fixture entities did not appear")
                    if not all(ha_matches(actual[entity], wanted) for entity, wanted in case["initial"].items()):
                        raise RuntimeError("Synthetic fixture initial state differs from pinned assertions")
                    env_file = Path(temp) / "mcp.env"
                    env_file.write_text(f"HOMEASSISTANT_URL=http://{ha_container}:8123\nHOMEASSISTANT_TOKEN={token}\n")
                    env_file.chmod(0o600)
                    progress(args.progress_file, args.case, "Starting ha-mcp in the isolated test network")
                    docker("run", "-d", "--name", mcp_container, "--network", network,
                           "--env-file", str(env_file), MCP_IMAGE, "sleep", "infinity")
                    os.environ["MATTBENCH_SYNTHETIC_HA_CONTAINER"] = ha_container
                    os.environ["MATTBENCH_SYNTHETIC_HA_TOKEN"] = token
                    os.environ["MATTBENCH_SYNTHETIC_MCP_CONTAINER"] = mcp_container
                    setup_done = time.monotonic()
                with deadline(EVALUATION_TIMEOUT, "HA evaluation"):
                    if args.preflight_only:
                        progress(args.progress_file, args.case, "Checking the synthetic service and state readback")
                        asyncio.run(apply_preflight_action(mcp_container, case["action"], list(case["expected"])))
                        actual = {entity: state(ha_container, token, entity) for entity in case["expected"]}
                        if not all(ha_matches(actual[entity], wanted) for entity, wanted in case["expected"].items()):
                            raise RuntimeError("Synthetic service did not produce pinned final state")
                        eval_done = time.monotonic()
                        outcome = "preflight_passed"
                        print(f"{args.case}: deterministic real ha-mcp preflight passed", flush=True)
                    else:
                        progress(args.progress_file, args.case, "Running model against the disposable Home Assistant")
                        print(f"Running {args.case} through real ha-mcp and disposable Synthetic Home", flush=True)
                        logs = run_eval(
                            tasks=[SUITE.task(entry.cases, plan.variants[0])], model=model_name,
                            max_tokens=SUITE.max_tokens, task_retry_attempts=0,
                            log_dir=str(SUITE.log_dir(run_id)), **GENERATION,
                        )
                        eval_done = time.monotonic()
                        for log in logs:
                            log_ids.append(log.eval.eval_id)
                            print(f"{log.eval.task}: {log.status}; log={log.location}")
                        if any(log.status != "success" for log in logs):
                            raise RuntimeError("Inspect HA evaluation did not complete successfully.")
                        outcome = "complete"
            except BaseException:
                failed = True
                outcome = "failed"
                raise
            finally:
                cleaning = True
                cleanup_started = time.monotonic()
                best_effort_progress(args.progress_file, args.case, "Cleaning up disposable containers and network")
                diagnostics = cleanup_resources(mcp_container, ha_container, network)
                for detail in diagnostics:
                    print(f"Disposable HA cleanup failed: {detail}", file=sys.stderr, flush=True)
                if diagnostics or interrupted:
                    outcome = "failed"
                finished = time.monotonic()
                metrics = {
                    "case_id": args.case, "status": outcome, "eval_ids": log_ids,
                    "setup_seconds": round((setup_done or cleanup_started) - clock_start, 3),
                    "evaluation_seconds": round((eval_done or cleanup_started) - setup_done, 3) if setup_done else 0,
                    "teardown_seconds": round(finished - cleanup_started, 3),
                    "total_wall_seconds": round(finished - clock_start, 3),
                }
                try:
                    write_json_atomic(ROOT / "artifacts/inspect/ha-timing" / f"{run_id}-{args.case}.json", metrics, indent=2)
                except Exception as error:
                    print(f"HA timing publication failed ({type(error).__name__}).", file=sys.stderr, flush=True)
                    outcome = "failed"
                    if not failed:
                        raise RuntimeError("HA timing publication failed.") from error
                finally:
                    best_effort_progress(args.progress_file, args.case,
                                         "HA case finished" if outcome in {"complete", "preflight_passed"} else "HA case failed")
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
    if outcome not in {"complete", "preflight_passed"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
