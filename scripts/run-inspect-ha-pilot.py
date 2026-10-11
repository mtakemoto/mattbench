"""Run one Inspect case against real ha-mcp and a disposable Synthetic Home.

Requires Docker and a local/private OpenAI-compatible model for scored runs.
Preflight needs no model. The first run fetches pinned public Synthetic Home
source, then reuses an ignored local cache. No production HA URL or token.
"""

import asyncio
import argparse
import inspect
import json
import os
import secrets
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
from inspect_pilot import ha_case, ha_cases
from scripts.run_inspect_settings import compatible_base, served_models

SYNTHETIC_SHA = "3a943b1346cad6c4d41f9c148921f87c9229bb0b"
HA_IMAGE = "mattbench-synthetic-ha:2026.10.1-v1"
MCP_IMAGE = "ghcr.io/homeassistant-ai/ha-mcp@sha256:f0a08038a230bd80a55332a1db1a955df48df018cfcc508c37c7f462c564c668"


def docker(*args: str) -> str:
    completed = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
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


def docker_python(container: str, source: str, data: str = "") -> str:
    completed = subprocess.run(
        ["docker", "exec", "-i", container, "python", "-c", source],
        input=data, capture_output=True, text=True, check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "no diagnostic"
        raise RuntimeError(f"Python in disposable container failed (exit {completed.returncode}): {detail[:240]}")
    return completed.stdout.strip()


def wait_http(container: str, timeout: int = 150) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            docker_python(container, "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8123/api/onboarding', timeout=2)")
            return
        except RuntimeError:
            time.sleep(2)
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
    source = (
        "import json,sys,urllib.request; p=json.load(sys.stdin); "
        "r=urllib.request.Request('http://127.0.0.1:8123/api/states/'+p['entity'], "
        "headers={'Authorization':'Bearer '+p['token']}); "
        "print(urllib.request.urlopen(r,timeout=10).read().decode())"
    )
    return json.loads(docker_python(container, source, json.dumps({"entity": entity_id, "token": token})))


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


def matches(actual: dict, wanted: dict) -> bool:
    return all(matches(actual.get(key, {}), value) if isinstance(value, dict) else actual.get(key) == value
               for key, value in wanted.items())


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
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(current) + "\n")
    temporary.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(ha_cases()), default="mxz_coordinator_target")
    parser.add_argument("--source", choices=("freetoken", "compatible"), default="freetoken")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--progress-file", default="")
    parser.add_argument("--preflight-only", action="store_true", help="Verify fixture and service path without a model")
    args = parser.parse_args()
    if args.run_id and (not args.run_id.isdigit() or not 14 <= len(args.run_id) <= 20):
        parser.error("Run ID must be a 14–20 digit UTC timestamp.")
    case = ha_cases()[args.case]
    progress(args.progress_file, args.case, "Validating model endpoint and pinned fixture", "preparing")
    if not args.preflight_only:
        if not args.base_url or not args.model:
            parser.error("Model and base URL are required for a benchmark run.")
        base = compatible_base(args.base_url)
        if args.model not in served_models(base):
            parser.error("Selected model is not served at that endpoint.")
    for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "FREETOKEN_API_KEY", "COMPATIBLE_API_KEY"):
        os.environ.pop(key, None)
    if not args.preflight_only:
        os.environ[f"{args.source.upper()}_BASE_URL"] = base
        os.environ[f"{args.source.upper()}_API_KEY"] = "local-no-secret"
    clock_start = time.monotonic()
    setup_done: float | None = None
    eval_done: float | None = None
    log_ids: list[str] = []
    outcome = "failed"
    suffix = secrets.token_hex(5)
    network = f"mattbench-ha-{suffix}"
    ha_container = f"mattbench-ha-{suffix}"
    mcp_container = f"mattbench-mcp-{suffix}"
    with tempfile.TemporaryDirectory(prefix="mattbench-ha-") as temp:
        progress(args.progress_file, args.case, "Preparing fictional fixture and isolated Home Assistant", "preparing")
        config = Path(temp) / "config"
        config.mkdir()
        (config / "configuration.yaml").write_text("default_config:\nhomeassistant:\n  unit_system: imperial\n")
        fixture = ROOT / case["fixture"]
        if not fixture.is_file() or fixture.parent != ROOT / "fixtures/ha":
            raise RuntimeError("Case fixture must be a pinned file in fixtures/ha")
        shutil.copy2(fixture, config / fixture.name)
        install_synthetic_component(config)
        try:
            progress(args.progress_file, args.case, "Starting disposable Home Assistant")
            docker("network", "create", "--internal", network)
            docker("run", "-d", "--name", ha_container, "--network", network,
                   "--mount", f"type=bind,src={config},dst=/config",
                   "--env", "TZ=UTC", HA_IMAGE)
            wait_http(ha_container)
            bootstrap_source = "import asyncio, aiohttp\n" + inspect.getsource(bootstrap)
            bootstrap_source += f"\nimport sys\nprint(asyncio.run(bootstrap('http://127.0.0.1:8123', sys.stdin.read().strip(), {fixture.name!r})))\n"
            token = docker_python(ha_container, bootstrap_source, secrets.token_urlsafe(24))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    actual = {entity: state(ha_container, token, entity) for entity in case["initial"]}
                    break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError("Synthetic fixture entities did not appear")
            if not all(matches(actual[entity], wanted) for entity, wanted in case["initial"].items()):
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
            if args.preflight_only:
                progress(args.progress_file, args.case, "Checking the synthetic service and state readback")
                asyncio.run(apply_preflight_action(mcp_container, case["action"], list(case["expected"])))
                actual = {entity: state(ha_container, token, entity) for entity in case["expected"]}
                if not all(matches(actual[entity], wanted) for entity, wanted in case["expected"].items()):
                    raise RuntimeError("Synthetic service did not produce pinned final state")
                eval_done = time.monotonic()
                outcome = "preflight_passed"
                print(f"{args.case}: deterministic real ha-mcp preflight passed", flush=True)
            else:
                progress(args.progress_file, args.case, "Running model against the disposable Home Assistant")
                print(f"Running {args.case} through real ha-mcp and disposable Synthetic Home", flush=True)
                logs = run_eval(
                    tasks=[ha_case(args.case)], model=f"openai-api/{args.source}/{args.model}",
                    model_args={"strict_tools": False}, temperature=0, max_tokens=512,
                    max_retries=0, timeout=120, max_samples=1, max_tasks=1,
                    log_dir=str(ROOT / "artifacts/inspect/ha" / (args.run_id or suffix)), display="plain",
                )
                eval_done = time.monotonic()
                for log in logs:
                    log_ids.append(log.eval.eval_id)
                    print(f"{log.eval.task}: {log.status}; log={log.location}")
                if any(log.status != "success" for log in logs):
                    raise SystemExit(1)
                outcome = "complete"
        finally:
            progress(args.progress_file, args.case, "Cleaning up disposable containers and network")
            cleanup_started = time.monotonic()
            cleanup_failed = False
            for command in (
                ["docker", "exec", "-u", "0", ha_container, "chown", "-R", f"{os.getuid()}:{os.getgid()}", "/config"],
                ["docker", "rm", "-f", mcp_container, ha_container],
                ["docker", "network", "rm", network],
            ):
                result = subprocess.run(command, capture_output=True)
                # Missing resources are expected when setup failed before creation.
                diagnostic = (result.stderr or b"").lower()
                missing = b"no such container" in diagnostic or b"no such network" in diagnostic or b"not found" in diagnostic
                if result.returncode and not missing:
                    cleanup_failed = True
            if cleanup_failed and outcome in {"complete", "preflight_passed"}:
                outcome = "failed"
                print("Could not restore ownership of disposable HA config during cleanup", file=sys.stderr, flush=True)
            finished = time.monotonic()
            metrics = {
                "case_id": args.case, "status": outcome, "eval_ids": log_ids,
                "setup_seconds": round((setup_done or cleanup_started) - clock_start, 3),
                "evaluation_seconds": round((eval_done or cleanup_started) - setup_done, 3) if setup_done else 0,
                "teardown_seconds": round(finished - cleanup_started, 3),
                "total_wall_seconds": round(finished - clock_start, 3),
            }
            timing_dir = ROOT / "artifacts/inspect/ha-timing"
            timing_dir.mkdir(parents=True, exist_ok=True)
            (timing_dir / f"{args.run_id or suffix}-{args.case}.json").write_text(json.dumps(metrics, indent=2) + "\n")
            progress(args.progress_file, args.case, "HA case finished" if outcome in {"complete", "preflight_passed"} else "HA case failed", "running" if args.progress_file else "running")
    if outcome not in {"complete", "preflight_passed"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
