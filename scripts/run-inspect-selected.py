"""Run the pinned Inspect smoke set for one explicitly selected model source."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval_set
from inspect_pilot import smoke
from scripts.run_inspect_settings import compatible_base, served_models


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("freetoken", "openrouter", "compatible"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--variant", choices=("base", "careful", "both"), required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    if not run_id.isdigit() or len(run_id) < 14 or len(run_id) > 20:
        parser.error("Run ID must be a 14–20 digit UTC timestamp.")

    if not args.model or len(args.model) > 160 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-:" for c in args.model):
        parser.error("Invalid model ID.")
    variants = ("base", "careful") if args.variant == "both" else (args.variant,)
    expected_calls = 2 * len(variants)
    if args.max_calls != expected_calls:
        parser.error(f"This fixture makes exactly {expected_calls} model calls; set --max-calls to {expected_calls}.")

    for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "FREETOKEN_API_KEY", "COMPATIBLE_API_KEY"):
        if key not in ("OPENROUTER_API_KEY",) or args.source != "openrouter":
            os.environ.pop(key, None)

    if args.source == "openrouter":
        if not os.environ.get("OPENROUTER_API_KEY"):
            parser.error("OPENROUTER_API_KEY is missing.")
        if args.cap_usd is None or not 0 < args.cap_usd <= 20:
            parser.error("Confirm an active OpenRouter workspace cap between $0 and $20 for this pilot.")
        os.environ["OPENROUTER_BASE_URL"] = "https://openrouter.ai/api/v1"
        model_name = f"openai-api/openrouter/{args.model}"
    else:
        base = compatible_base(args.base_url)
        if args.model not in served_models(base):
            parser.error("Selected model is not served at that endpoint.")
        service = args.source
        os.environ[f"{service.upper()}_BASE_URL"] = base
        os.environ[f"{service.upper()}_API_KEY"] = "local-no-secret"
        model_name = f"openai-api/{service}/{args.model}"

    print(f"Running {args.source}/{args.model}, {args.variant}, {expected_calls} calls maximum", flush=True)
    success, logs = eval_set(
        tasks=[smoke(variant) for variant in variants],
        model=model_name,
        model_args={"strict_tools": False},
        temperature=0,
        max_tokens=512,
        max_retries=0,
        timeout=120,
        max_samples=1,
        max_tasks=1,
        log_dir=str(ROOT / "artifacts/inspect/selected" / run_id),
        display="plain",
    )
    for log in logs:
        print(f"{log.eval.task}: {log.status}; log={log.location}", flush=True)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
