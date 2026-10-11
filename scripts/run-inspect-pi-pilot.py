"""Run one real Pi instruction case through Inspect and local FreeToken."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval as run_eval
from inspect_pi import pi_scope
from scripts.run_inspect_settings import local_settings, set_local_model_environment


def main() -> None:
    base, model = local_settings()
    set_local_model_environment(base)
    logs = run_eval(
        tasks=[pi_scope()], model=f"openai-api/freetoken/{model}",
        model_args={"strict_tools": False}, temperature=0, max_tokens=2048,
        max_retries=0, timeout=120, max_samples=1, max_tasks=1,
        log_dir=str(ROOT / "artifacts/inspect"), display="plain",
    )
    for log in logs:
        print(f"{log.eval.task}: {log.status}; log={log.location}")
    if any(log.status != "success" for log in logs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
