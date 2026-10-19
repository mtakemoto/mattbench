"""Run the pinned Inspect smoke set for one explicitly selected model source."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval_set
from inspect_pilot import smoke
from scripts.execution_plan import build_plan, load_plan, require_calls, run_id
from scripts.run_inspect_settings import prepare_provider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("freetoken", "openrouter", "compatible"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--variant", choices=("base", "careful", "both"), required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--plan-file", type=Path)
    args = parser.parse_args()
    try:
        identifier = run_id(args.run_id)
        plan = load_plan(args.plan_file) if args.plan_file else build_plan(args.variant)
        variants = ("base", "careful") if args.variant == "both" else (args.variant,)
        if plan.variants != variants or not plan.smoke_cases or plan.ha_cases:
            raise ValueError("Execution plan does not match the selected smoke prompt variants.")
        require_calls(plan, args.max_calls, scope="Smoke run")
        model_name = prepare_provider(args.source, args.model, base_url=args.base_url, cap_usd=args.cap_usd)
    except (ValueError, OSError) as error:
        parser.error(str(error))

    print(f"Running {args.source}/{args.model}, {args.variant}, {plan.max_calls} calls maximum", flush=True)
    success, logs = eval_set(
        tasks=[smoke(variant, rows=plan.smoke_cases) for variant in variants],
        model=model_name,
        model_args={"strict_tools": False},
        temperature=0,
        max_tokens=512,
        max_retries=0,
        retry_attempts=0,
        retry_on_error=0,
        timeout=120,
        max_samples=1,
        max_tasks=1,
        log_dir=str(ROOT / "artifacts/inspect/selected" / identifier),
        display="plain",
    )
    for log in logs:
        print(f"{log.eval.task}: {log.status}; log={log.location}", flush=True)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
