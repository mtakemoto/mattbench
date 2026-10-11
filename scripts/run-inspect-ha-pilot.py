"""Run one Inspect case against real ha-mcp and a disposable Synthetic Home.

Requires Docker, local FreeToken, and network access to fetch the pinned public
Synthetic Home source on first run. Never accepts a production HA URL or token.
"""

import asyncio
import io
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inspect_ai import eval as run_eval
from inspect_pilot import ha_chained
from scripts.run_inspect_settings import local_settings, set_local_model_environment

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
    with urlopen(archive_url, timeout=60) as response:
        archive = tarfile.open(fileobj=io.BytesIO(response.read()), mode="r:gz")
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


async def bootstrap(ha_url: str, password: str) -> str:
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
                                headers=headers, json={"config_filename": "inspect-climate.yaml"}) as response:
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


def main() -> None:
    base, model = local_settings()
    set_local_model_environment(base)
    suffix = secrets.token_hex(5)
    network = f"mattbench-ha-{suffix}"
    ha_container = f"mattbench-ha-{suffix}"
    mcp_container = f"mattbench-mcp-{suffix}"
    with tempfile.TemporaryDirectory(prefix="mattbench-ha-") as temp:
        config = Path(temp) / "config"
        config.mkdir()
        (config / "configuration.yaml").write_text("default_config:\nhomeassistant:\n  unit_system: imperial\n")
        shutil.copy2(ROOT / "fixtures/ha/inspect-climate.yaml", config / "inspect-climate.yaml")
        install_synthetic_component(config)
        docker("network", "create", "--internal", network)
        try:
            docker("run", "-d", "--name", ha_container, "--network", network,
                   "--mount", f"type=bind,src={config},dst=/config",
                   "--env", "TZ=UTC", HA_IMAGE)
            wait_http(ha_container)
            bootstrap_source = "import asyncio, aiohttp\n" + inspect.getsource(bootstrap)
            bootstrap_source += "\nimport sys\nprint(asyncio.run(bootstrap('http://127.0.0.1:8123', sys.stdin.read().strip())))\n"
            token = docker_python(ha_container, bootstrap_source, secrets.token_urlsafe(24))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    coordinator = state(ha_container, token, "climate.north_room_coordinator")
                    head = state(ha_container, token, "climate.north_room_head")
                    break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError("Synthetic climate entities did not appear")
            if coordinator["attributes"].get("temperature") != 70 or head["attributes"].get("temperature") != 74:
                raise RuntimeError(
                    "Synthetic climate initial targets differ: "
                    f"coordinator={coordinator['attributes'].get('temperature')!r}, "
                    f"head={head['attributes'].get('temperature')!r}"
                )
            env_file = Path(temp) / "mcp.env"
            env_file.write_text(f"HOMEASSISTANT_URL=http://{ha_container}:8123\nHOMEASSISTANT_TOKEN={token}\n")
            env_file.chmod(0o600)
            docker("run", "-d", "--name", mcp_container, "--network", network,
                   "--env-file", str(env_file), MCP_IMAGE, "sleep", "infinity")
            os.environ["MATTBENCH_SYNTHETIC_HA_CONTAINER"] = ha_container
            os.environ["MATTBENCH_SYNTHETIC_HA_TOKEN"] = token
            os.environ["MATTBENCH_SYNTHETIC_MCP_CONTAINER"] = mcp_container
            print("Running real ha-mcp against disposable Synthetic Home", flush=True)
            logs = run_eval(
                tasks=[ha_chained()], model=f"openai-api/freetoken/{model}",
                model_args={"strict_tools": False}, temperature=0, max_tokens=512,
                max_retries=0, timeout=120, max_samples=1, max_tasks=1,
                log_dir=str(ROOT / "artifacts/inspect"), display="plain",
            )
            for log in logs:
                print(f"{log.eval.task}: {log.status}; log={log.location}")
            if any(log.status != "success" for log in logs):
                raise SystemExit(1)
        finally:
            subprocess.run(["docker", "exec", "-u", "0", ha_container, "chown", "-R", f"{os.getuid()}:{os.getgid()}", "/config"], capture_output=True)
            subprocess.run(["docker", "rm", "-f", mcp_container, ha_container], capture_output=True)
            subprocess.run(["docker", "network", "rm", network], capture_output=True)


if __name__ == "__main__":
    main()
