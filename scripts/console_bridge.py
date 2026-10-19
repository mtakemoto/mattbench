"""JSON answers for the web console: the suite catalog and endpoint validation.

Prints one JSON object on stdout. Errors print ``{"error": ...}`` and exit 1;
messages come from our validators and never include credentials.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_inspect_settings import local_config, read_env_file, resolve_base_url
from suites import registry


def describe() -> dict:
    """Non-secret settings and every registered suite with its cases."""
    try:
        local_base, local_model = local_config()
    except ValueError:
        local_base, local_model = "", ""
    openrouter_ready = bool(os.environ.get("OPENROUTER_API_KEY") or read_env_file().get("OPENROUTER_API_KEY"))
    return {"settings": {"localBase": local_base, "localModel": local_model, "openrouterReady": openrouter_ready},
            "suites": [suite.describe() for suite in registry().values()]}


def endpoint(request: dict) -> dict:
    if not isinstance(request, dict):
        raise ValueError("Endpoint request must be a JSON object.")
    return {"baseUrl": resolve_base_url(request.get("source"), request.get("baseUrl", ""))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--describe", action="store_true", help="Print settings and the suite catalog")
    mode.add_argument("--endpoint", action="store_true", help="Validate {source, baseUrl} read from stdin")
    args = parser.parse_args()
    try:
        print(json.dumps(describe() if args.describe else endpoint(json.load(sys.stdin))))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
