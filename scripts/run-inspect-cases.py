"""Evaluate one suite entry of a frozen plan in-process with Inspect.

The suite orchestrator launches this once per plan entry. Suites that need
their own process lifecycle (for example disposable containers) override
``Suite.command`` and use a dedicated runner instead.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval_set
from scripts import case_progress
from scripts.execution_plan import load_plan, require_calls, run_id
from scripts.run_inspect_settings import GENERATION, SOURCES, prepare_provider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--case", action="append", default=[], help="Case ID within the suite; repeat for several")
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    try:
        identifier = run_id(args.run_id)
        plan = load_plan(args.plan_file)
        entry = plan.entry(args.suite, args.case)
        require_calls(entry, args.max_calls, scope=entry.label)
        model_name = prepare_provider(args.source, args.model, base_url=args.base_url, cap_usd=args.cap_usd)
    except (ValueError, OSError) as error:
        parser.error(str(error))

    case_progress.install()
    print(f"Running {entry.label} on {args.source}/{args.model}, {entry.model_calls} calls maximum", flush=True)
    success, logs = eval_set(
        tasks=[entry.suite.task(entry.cases, variant) for variant in plan.variants],
        model=model_name,
        max_tokens=entry.suite.max_tokens,
        retry_attempts=0,
        log_dir=str(entry.suite.log_dir(identifier)),
        **GENERATION,
    )
    for log in logs:
        print(f"{log.eval.task}: {log.status}; log={log.location}", flush=True)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
