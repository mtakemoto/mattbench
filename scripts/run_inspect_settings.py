"""Provider configuration shared by Inspect launchers and the plan bridge."""

import ipaddress
import json
import math
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("freetoken", "openrouter", "compatible")
"""Model sources: loopback FreeToken, hosted OpenRouter, or a private OpenAI-compatible endpoint."""
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
GENERATION = {
    "model_args": {"strict_tools": False},
    "temperature": 0,
    "max_retries": 0,
    "retry_on_error": 0,
    "timeout": 120,
    "max_samples": 1,
    "max_tasks": 1,
    "display": "plain",
}
"""Inspect settings every scored run shares, so results stay comparable; suites set max_tokens."""
MODEL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-:~")
SOURCE_KEYS = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "FREETOKEN_API_KEY", "COMPATIBLE_API_KEY")

def validate_model(model: str) -> str:
    if not isinstance(model, str) or not model or len(model) > 160 or any(char not in MODEL_CHARS for char in model):
        raise ValueError("Invalid model ID.")
    return model


def is_free_model(model: str) -> bool:
    """OpenRouter marks zero-cost endpoints with the ':free' model-ID suffix."""
    return model.endswith(":free")


def validate_cap(cap_usd: float | None) -> float:
    if isinstance(cap_usd, bool) or not isinstance(cap_usd, (int, float)) or not math.isfinite(cap_usd) or not 0 < cap_usd <= 20:
        raise ValueError("Confirm an active OpenRouter workspace cap between $0 and $20.")
    return cap_usd


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def resolve_base_url(source: str, base_url: str = "") -> str:
    """Validated endpoint for a source; FreeToken falls back to the configured local endpoint."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}.")
    if source == "openrouter":
        return ""
    if source == "freetoken" and not base_url:
        base_url, _ = local_config()
    return compatible_base(base_url, loopback_only=source == "freetoken")


def prepare_provider(source: str, model: str, *, base_url: str = "", cap_usd: float | None = None,
                     discover: bool = True) -> str:
    """Validate source before mutating environment; return the Inspect model name."""
    validate_model(model)
    base = resolve_base_url(source, base_url) or OPENROUTER_BASE
    if source == "openrouter":
        if not is_free_model(model) or cap_usd is not None:
            validate_cap(cap_usd)
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY is missing.")
    elif discover and model not in served_models(base):
        raise ValueError("Selected model is not served at that endpoint.")
    for key in SOURCE_KEYS:
        if source != "openrouter" or key != "OPENROUTER_API_KEY":
            os.environ.pop(key, None)
    os.environ[f"{source.upper()}_BASE_URL"] = base
    if source != "openrouter":
        os.environ[f"{source.upper()}_API_KEY"] = "local-no-secret"
    return f"openai-api/{source}/{model}"


def compatible_base(value: str, *, loopback_only: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("Endpoint must be a URL string.")
    url = urlparse(value)
    host = url.hostname or ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if host != "localhost":
            raise ValueError("Use localhost or a literal private or loopback IP address.") from None
    else:
        allowed = (ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128")) if loopback_only else (
            ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"), ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("::1/128"), ipaddress.ip_network("fc00::/7"),
        )
        if not any(address in network for network in allowed):
            raise ValueError("FreeToken must be loopback-only." if loopback_only else
                             "Compatible endpoints must be on loopback or a private network.")
    if (url.scheme != "http" or url.path.rstrip("/") != "/v1" or url.username
            or url.password or url.query or url.fragment or not url.netloc):
        raise ValueError("Endpoint must be plain HTTP and end in /v1, without credentials or a query.")
    try:
        _ = url.port
    except ValueError as error:
        raise ValueError("Endpoint port is invalid.") from error
    return value.rstrip("/")


def served_models(base: str) -> set[str]:
    request = Request(base + "/models", headers={"Authorization": "Bearer local-no-secret"})
    with urlopen(request, timeout=8) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Model endpoint returned invalid JSON: expected a data array.")
    if any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in payload["data"]):
        raise ValueError("Model endpoint returned invalid JSON: expected model IDs.")
    return {row["id"] for row in payload["data"]}


def read_env_file(path: Path | None = None) -> dict[str, str]:
    """Parse private dotenv values in memory; callers must never print this mapping."""
    file = path or ROOT / ".env"
    if not file.exists():
        return {}
    values = {}
    for line in file.read_text().splitlines():
        key, sep, value = line.partition("=")
        key = key.strip()
        if sep and key and not key.startswith("#"):
            values[key] = _unquote(value)
    return values


def local_config() -> tuple[str, str]:
    """Read settings without network access; do not expose credentials."""
    values = read_env_file()
    base = os.environ.get("MATTBENCH_LOCAL_BASE_URL") or values.get("MATTBENCH_LOCAL_BASE_URL")
    model = os.environ.get("MATTBENCH_LOCAL_MODEL") or values.get("MATTBENCH_LOCAL_MODEL")
    if not base or not model:
        raise ValueError("Set MATTBENCH_LOCAL_BASE_URL and MATTBENCH_LOCAL_MODEL.")
    return compatible_base(_unquote(base), loopback_only=True), validate_model(_unquote(model))


def local_settings() -> tuple[str, str]:
    try:
        base, model = local_config()
        if model not in served_models(base):
            raise ValueError("Configured model is not present at the local endpoint.")
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return base, model


def set_local_model_environment(base: str) -> None:
    compatible_base(base, loopback_only=True)
    for key in SOURCE_KEYS:
        os.environ.pop(key, None)
    os.environ["FREETOKEN_BASE_URL"] = base
    os.environ["FREETOKEN_API_KEY"] = "local-no-secret"
