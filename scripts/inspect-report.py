"""Export small, dashboard-ready summaries from local Inspect eval logs."""

import json
from pathlib import Path

from inspect_ai.log import read_eval_log


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "artifacts/inspect"


def passed(value: object) -> bool | None:
    if value in ("C", True, 1):
        return True
    if value in ("I", False, 0):
        return False
    return None


def main() -> None:
    rows = []
    timing_by_eval = {}
    for timing_path in (LOG_DIR / "ha-timing").glob("*.json"):
        timing = json.loads(timing_path.read_text())
        for eval_id in timing.get("eval_ids", []):
            timing_by_eval[eval_id] = {key: timing.get(key) for key in (
                "setup_seconds", "evaluation_seconds", "teardown_seconds", "total_wall_seconds"
            )}
    for path in sorted(LOG_DIR.rglob("*.eval")):
        log = read_eval_log(path)
        relative_parts = path.relative_to(LOG_DIR).parts
        launcher_run_id = relative_parts[1] if len(relative_parts) > 2 and relative_parts[0] in {"selected", "ha"} and relative_parts[1].isdigit() and 14 <= len(relative_parts[1]) <= 20 else None
        for sample in log.samples or []:
            scores = {name: score.value for name, score in (sample.scores or {}).items()}
            score_metadata = {
                name: {
                    key: value for key, value in (score.metadata or {}).items()
                    if key in {"harness_tool_calls", "harness_tool_errors", "harness_tool_names"}
                }
                for name, score in (sample.scores or {}).items()
            }
            usage = {
                model: entry.model_dump(
                    include={"input_tokens", "output_tokens", "total_tokens", "total_cost"}
                )
                for model, entry in (sample.model_usage or {}).items()
            }
            rows.append(
                {
                    "task": log.eval.task,
                    "run_id": log.eval.run_id,
                    "launcher_run_id": launcher_run_id,
                    "eval_id": log.eval.eval_id,
                    "sample_id": sample.id,
                    "category": (sample.metadata or {}).get("category"),
                    "prompt_variant": (sample.metadata or {}).get("prompt_variant", "base"),
                    "status": log.status,
                    "model": log.eval.model,
                    "concrete_response_model": getattr(sample.output, "model", None),
                    "task_version": log.eval.task_version,
                    "fixture": (sample.metadata or {}).get("fixture"),
                    "inference": log.eval.model_generate_config.model_dump(
                        include={"temperature", "max_tokens", "max_retries", "timeout"}
                    ),
                    "model_args": log.eval.model_args,
                    "inspect_version": (log.eval.packages or {}).get("inspect_ai"),
                    "scores": scores,
                    "score_metadata": score_metadata,
                    "passed": all(passed(value) is True for value in scores.values()) if scores else None,
                    "latency_seconds": sample.total_time,
                    "run_timing": timing_by_eval.get(log.eval.eval_id),
                    "usage": usage,
                    "tool_calls": sum(event.event == "tool" for event in sample.events),
                    "started_at": sample.started_at,
                    "log_file": str(path.relative_to(LOG_DIR)),
                }
            )
    output = LOG_DIR / "summary.json"
    output.write_text(json.dumps({"schema_version": 1, "rows": rows}, indent=2, default=str) + "\n")
    print(f"Wrote {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()
