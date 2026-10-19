"""Compare every prompt variant of the smoke suite on FreeToken, or on Inspect's mock model."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval_set
from scripts.execution_plan import build_plan, load_plan, require_calls
from scripts.run_inspect_settings import GENERATION, local_settings, set_local_model_environment
from suites.smoke import SUITE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true", help="Use Inspect's deterministic mock model to test report plumbing")
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--max-calls", type=int)
    args = parser.parse_args()
    try:
        plan = load_plan(args.plan_file) if args.plan_file else build_plan([SUITE.id], SUITE.variants)
        if plan.variants != SUITE.variants or {case.suite for case in plan.cases} != {SUITE.id}:
            raise ValueError(f"Prompt matrix requires a {SUITE.label} plan with every prompt variant.")
        if args.max_calls is not None:
            require_calls(plan, args.max_calls, scope="Prompt matrix")
    except ValueError as error:
        parser.error(str(error))
    if args.mock:
        model_name, directory, model_args = "mockllm/model", "prompt-matrix-mock", {}
    else:
        base, model = local_settings()
        set_local_model_environment(base)
        model_name, directory, model_args = f"openai-api/freetoken/{model}", "prompt-matrix", GENERATION["model_args"]
    success, logs = eval_set(
        tasks=[SUITE.task(plan.cases, variant) for variant in plan.variants],
        model=model_name,
        max_tokens=SUITE.max_tokens,
        retry_attempts=0,
        log_dir=str(ROOT / "artifacts/inspect" / directory),
        **{**GENERATION, "model_args": model_args},
    )
    for log in logs:
        print(f"{log.eval.task}: {log.status}; log={log.location}")
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
