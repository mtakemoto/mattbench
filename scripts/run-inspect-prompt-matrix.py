"""Compare the pinned smoke tasks with base and careful prompts on FreeToken."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval_set
from inspect_pilot import smoke
from scripts.run_inspect_settings import local_settings, set_local_model_environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true", help="Use Inspect's deterministic mock model to test report plumbing")
    args = parser.parse_args()
    if args.mock:
        model_name = "mockllm/model"
        directory = "prompt-matrix-mock"
    else:
        base, model = local_settings()
        set_local_model_environment(base)
        model_name = f"openai-api/freetoken/{model}"
        directory = "prompt-matrix"
    success, logs = eval_set(
        tasks=[smoke("base"), smoke("careful")],
        model=model_name,
        model_args={} if args.mock else {"strict_tools": False},
        temperature=0,
        max_tokens=512,
        max_retries=0,
        timeout=120,
        max_samples=1,
        max_tasks=1,
        log_dir=str(ROOT / f"artifacts/inspect/{directory}"),
        display="plain",
    )
    for log in logs:
        print(f"{log.eval.task}: {log.status}; log={log.location}")
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
