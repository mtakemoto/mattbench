"""Run the laptop shopping benchmark task for one explicitly selected model source."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval_set
from inspect_laptops import laptop_shopping
from scripts.execution_plan import run_id as generate_run_id
from scripts.run_inspect_settings import prepare_provider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("freetoken", "openrouter", "compatible"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--max-calls", type=int, default=13)
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--progress-file", type=Path)
    args = parser.parse_args()

    try:
        identifier = generate_run_id(args.run_id)
        model_name = prepare_provider(args.source, args.model, base_url=args.base_url, cap_usd=args.cap_usd)
    except (ValueError, OSError) as error:
        parser.error(str(error))

    print(f"Running laptop benchmark on {args.source}/{args.model}, budget {args.max_calls} calls maximum", flush=True)
    success, logs = eval_set(
        tasks=[laptop_shopping()],
        model=model_name,
        model_args={"strict_tools": False},
        temperature=0,
        max_tokens=512,
        max_retries=0,
        retry_attempts=0,
        retry_on_error=0,
        timeout=180,
        max_samples=1,
        max_tasks=1,
        log_dir=str(ROOT / "artifacts/inspect/laptops" / identifier),
        display="plain",
    )
    for log in logs:
        print(f"{log.eval.task}: {log.status}; log={log.location}", flush=True)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
