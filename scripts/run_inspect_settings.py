"""Local-only model settings shared by Inspect pilot launchers."""

import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def local_settings() -> tuple[str, str]:
    values = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key in {"MATTBENCH_LOCAL_BASE_URL", "MATTBENCH_LOCAL_MODEL"}:
                values[key] = value.strip()
    base = os.environ.get("MATTBENCH_LOCAL_BASE_URL") or values.get("MATTBENCH_LOCAL_BASE_URL")
    model = os.environ.get("MATTBENCH_LOCAL_MODEL") or values.get("MATTBENCH_LOCAL_MODEL")
    if not base or not model:
        raise SystemExit("Set MATTBENCH_LOCAL_BASE_URL and MATTBENCH_LOCAL_MODEL.")
    url = urlparse(base)
    if (
        url.scheme != "http"
        or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or url.path.rstrip("/") != "/v1"
        or url.username or url.password or url.query or url.fragment
    ):
        raise SystemExit("Local base URL must be plain HTTP loopback ending in /v1.")
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-" for char in model):
        raise SystemExit("Local model ID has unsupported characters.")
    with urlopen(base.rstrip("/") + "/models", timeout=5) as response:
        ids = {entry.get("id") for entry in json.load(response).get("data", [])}
    if model not in ids:
        raise SystemExit("Configured model is not present at the local endpoint.")
    return base.rstrip("/"), model


def set_local_model_environment(base: str) -> None:
    for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)
    os.environ["FREETOKEN_BASE_URL"] = base
    os.environ["FREETOKEN_API_KEY"] = "local-no-secret"
