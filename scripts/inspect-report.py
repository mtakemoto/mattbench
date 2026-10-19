"""Export small, dashboard-ready summaries from local Inspect eval logs."""

import json
import math
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.inspect_results import launcher_run_id, sample_outcome
from scripts.json_files import write_json_atomic


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "artifacts/inspect"


def read_billing_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise ValueError("Invalid billing envelope")
    rows = payload["rows"]
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in ("eval_id", "sample_id")) or "cost_usd" not in row:
            raise ValueError("Invalid billing row identity")
        for key in ("cost_usd", "partial_cost_usd"):
            value = row.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise ValueError("Invalid billed cost")
        for key in ("providers", "routed_models"):
            if not isinstance(row.get(key), list) or not all(isinstance(value, str) for value in row[key]):
                raise ValueError("Invalid billing model/provider list")
        counters = ("generation_attempts", "available_ids", "queried_ids", "billed_calls", "unknown_attempts", "lookup_failures")
        if "complete" not in row:
            # Old artifacts counted only events with IDs. Their claimed exact totals
            # cannot prove full accounting, so expose them solely as partial amounts.
            row["partial_cost_usd"] = row["cost_usd"]
            row["cost_usd"] = None
            row["complete"] = False
            row["accounting_legacy"] = True
            continue
        if not isinstance(row["complete"], bool) or "partial_cost_usd" not in row or any(
            key not in row or type(row[key]) is not int or row[key] < 0 for key in counters
        ):
            raise ValueError("Invalid billing completeness or counters")
        if (row["complete"] and (row["cost_usd"] is None or row["partial_cost_usd"] is not None or row["unknown_attempts"])) or (
            not row["complete"] and (row["cost_usd"] is not None or row["partial_cost_usd"] is None)
        ):
            raise ValueError("Contradictory billing completeness")
    safe_keys = {
        "eval_id", "sample_id", "complete", "cost_usd", "partial_cost_usd",
        "generation_attempts", "expected_calls", "available_ids", "queried_ids",
        "billed_calls", "unknown_attempts", "lookup_failures",
        "shared_generation_ids", "providers", "routed_models", "accounting_legacy",
    }
    return [{key: value for key, value in row.items() if key in safe_keys} for row in rows]


def read_timing(path: Path) -> tuple[list[str], dict]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("eval_ids"), list) or not all(
        isinstance(value, str) for value in payload["eval_ids"]
    ):
        raise ValueError("Invalid timing envelope")
    keys = ("setup_seconds", "evaluation_seconds", "teardown_seconds", "total_wall_seconds")
    for key in keys:
        value = payload.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
            raise ValueError("Invalid timing duration")
    return payload["eval_ids"], {key: payload.get(key) for key in keys}


def export_eval(path: Path, timing_by_eval: dict, billing_by_sample: dict) -> list[dict]:
    log = read_eval_log(path)
    if not isinstance(log.eval.eval_id, str) or not isinstance(log.eval.model, str):
        raise ValueError("Invalid evaluation identity")
    rows = []
    relative_log = path.relative_to(LOG_DIR)
    for sample in log.samples or []:
        billing = billing_by_sample.get((log.eval.eval_id, sample.id))
        scores = {name: score.value for name, score in (sample.scores or {}).items()}
        score_metadata = {
            name: {
                key: value for key, value in (score.metadata or {}).items()
                if key in {
                    "harness_tool_calls", "harness_tool_errors", "harness_tool_names",
                    "state_correct", "trace_valid", "trace_reason",
                    "objective_preserved_global", "objective_preserved_project",
                    "objective_scoped_placement",
                    "objective_checks_passed",
                    "semantic_review_required", "semantic_review_status", "semantic_review_reason",
                }
            }
            for name, score in (sample.scores or {}).items()
        }
        if log.eval.task == "pi_scope" and str(log.eval.task_version) == "1":
            score_metadata.setdefault("instruction_scope_state", {}).update({
                "semantic_review_required": True,
                "semantic_review_status": "pending",
                "semantic_review_reason": "Legacy keyword scores do not establish semantic correctness; archived scores are retained, not regraded.",
            })
        usage = {
            model: entry.model_dump(
                include={"input_tokens", "output_tokens", "total_tokens", "total_cost"}
            )
            for model, entry in (sample.model_usage or {}).items()
        }
        if billing and billing.get("complete") is True and billing["cost_usd"] is not None and len(usage) == 1:
            next(iter(usage.values()))["total_cost"] = billing["cost_usd"]
        rows.append({
            "task": log.eval.task,
            "run_id": log.eval.run_id,
            "launcher_run_id": launcher_run_id(relative_log),
            "eval_id": log.eval.eval_id,
            "sample_id": sample.id,
            "category": (sample.metadata or {}).get("category"),
            "prompt_variant": (sample.metadata or {}).get("prompt_variant", "base"),
            "status": log.status,
            "model": log.eval.model,
            "concrete_response_model": getattr(sample.output, "model", None),
            "routed_models": billing["routed_models"] if billing else [],
            "providers": billing["providers"] if billing else [],
            "billing": billing,
            "task_version": log.eval.task_version,
            "fixture": (sample.metadata or {}).get("fixture"),
            "inference": log.eval.model_generate_config.model_dump(
                include={"temperature", "max_tokens", "max_retries", "timeout"}
            ),
            "model_args": log.eval.model_args,
            "inspect_version": (log.eval.packages or {}).get("inspect_ai"),
            "scores": scores,
            "score_metadata": score_metadata,
            "score_explanation": (sample.scores or {}).get("synthetic_ha_state").explanation if "synthetic_ha_state" in (sample.scores or {}) else None,
            "passed": sample_outcome(scores.values(), score_metadata.values()),
            "truncated": getattr(sample.output, "stop_reason", None) == "max_tokens",
            "latency_seconds": sample.total_time,
            "run_timing": timing_by_eval.get(log.eval.eval_id),
            "usage": usage,
            "tool_calls": sum(event.event == "tool" for event in sample.events),
            "model_calls": sum(event.event == "model" for event in sample.events),
            "started_at": sample.started_at,
            "log_file": str(relative_log),
        })
    return rows


def main() -> None:
    rows = []
    warnings = []
    timing_by_eval = {}
    billing_by_sample = {}
    for billing_path in sorted((LOG_DIR / "openrouter-billing").glob("*.json")):
        try:
            items = read_billing_rows(billing_path)
        except Exception:
            warnings.append("Skipped one invalid billing artifact; report is incomplete.")
            continue
        for item in items:
            billing_by_sample[(item["eval_id"], item["sample_id"])] = item
    for timing_path in sorted((LOG_DIR / "ha-timing").glob("*.json")):
        try:
            eval_ids, timing = read_timing(timing_path)
        except Exception:
            warnings.append("Skipped one invalid timing artifact; report is incomplete.")
            continue
        for eval_id in eval_ids:
            timing_by_eval[eval_id] = timing
    for path in sorted(LOG_DIR.rglob("*.eval")):
        try:
            rows.extend(export_eval(path, timing_by_eval, billing_by_sample))
        except Exception:
            warnings.append("Skipped one invalid evaluation artifact; report is incomplete.")
    incomplete = sum(row["billing"].get("complete") is not True for row in rows if row["billing"] is not None)
    if incomplete:
        warnings.append(f"Billing incomplete for {incomplete} sample(s); exact cost is unknown.")
    unbilled = sum(
        row["billing"] is None and row["model"].startswith("openai-api/openrouter/")
        for row in rows
    )
    if unbilled:
        warnings.append(f"Billing metadata unavailable for {unbilled} OpenRouter sample(s); exact cost is unknown.")
    output = LOG_DIR / "summary.json"
    write_json_atomic(output, {"schema_version": 1, "rows": rows, "incomplete_report": bool(warnings), "warnings": warnings},
                      indent=2, default=str)
    print(f"Wrote {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()
