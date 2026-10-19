"""Run the Inspect pilot only against the configured loopback FreeToken model."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval as run_eval
from inspect_pilot import coding
from suites.smoke.task import smoke
from scripts.run_inspect_settings import local_settings, set_local_model_environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    tasks = {task.__name__: task for task in (smoke, coding)}
    parser.add_argument("--task", choices=(*tasks, "all"), default="all")
    args = parser.parse_args()
    base, model = local_settings()
    set_local_model_environment(base)
    print(f"Inspect local pilot: {model}", flush=True)
    selected = list(tasks) if args.task == "all" else [args.task]
    logs = run_eval(
        tasks=[tasks[name]() for name in selected],
        model=f"openai-api/freetoken/{model}",
        model_args={"strict_tools": False},
        temperature=0,
        max_tokens=512,
        max_retries=0,
        timeout=120,
        max_samples=1,
        max_tasks=1,
        log_dir=str(ROOT / "artifacts/inspect"),
        display="plain",
    )
    for log in logs:
        print(f"{log.eval.task}: {log.status}; log={log.location}")
    if any(log.status != "success" for log in logs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
