"""Fetch exact billed costs for one finished OpenRouter run without storing request IDs."""

import argparse
import json
import math
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from inspect_ai.log import read_eval_log


ROOT = Path(__file__).resolve().parents[1]


def generation(generation_id: str, key: str) -> dict:
    if not re.fullmatch(r"gen-[A-Za-z0-9_-]+", generation_id):
        raise ValueError("Inspect did not record an OpenRouter generation ID")
    url = "https://openrouter.ai/api/v1/generation?" + urlencode({"id": generation_id})
    request = Request(url, headers={"Authorization": "Bearer " + key})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=12) as response:
                data = json.load(response)["data"]
            amount = data.get("total_cost")
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
                raise ValueError("Generation has no billed cost")
            return {"cost_usd": amount, "provider": data.get("provider_name"), "model": data.get("model")}
        except HTTPError as error:
            if error.code != 404 or attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("Generation billing unavailable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{14,20}", args.run_id):
        parser.error("Run ID must be a 14–20 digit UTC timestamp.")
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        parser.error("OPENROUTER_API_KEY is missing.")

    jobs = []
    # Launchers write to <suite>/<run_id>/; bill every suite that ran under this ID.
    for path in sorted((ROOT / "artifacts/inspect").glob(f"*/{args.run_id}/*.eval")):
        log = read_eval_log(path)
        if not log.eval.model.startswith("openai-api/openrouter/"):
            continue
        for sample in log.samples or []:
            attempts = [
                getattr(getattr(event, "output", None), "response_id", None)
                for event in sample.events or [] if event.event == "model"
            ]
            attempts = [
                generation_id if isinstance(generation_id, str) and re.fullmatch(r"gen-[A-Za-z0-9_-]+", generation_id) else None
                for generation_id in attempts
            ]
            jobs.append((log.eval.eval_id, sample.id, attempts))

    ids = sorted({
        generation_id for _, _, attempts in jobs
        for generation_id in attempts if generation_id
    })
    billed = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {generation_id: pool.submit(generation, generation_id, key) for generation_id in ids}
        for generation_id, future in futures.items():
            try:
                billed[generation_id] = future.result()
            except (ValueError, KeyError, TypeError, AttributeError, HTTPError, OSError, TimeoutError):
                pass

    # A generation ID can appear in multiple samples. Attribute its charge once,
    # to the first sample, while retaining the lookup result in all affected rows.
    owned_ids = set()
    rows = []
    for eval_id, sample_id, attempts in jobs:
        sample_ids = set(generation_id for generation_id in attempts if generation_id)
        own_ids = sample_ids - owned_ids
        shared_ids = sample_ids & owned_ids
        owned_ids.update(own_ids)
        items = [billed[generation_id] for generation_id in own_ids if generation_id in billed]
        available_items = [billed[generation_id] for generation_id in sample_ids if generation_id in billed]
        missing_ids = sum(not generation_id for generation_id in attempts)
        lookup_failures = len(sample_ids - billed.keys())
        complete = bool(attempts) and not missing_ids and not lookup_failures
        accounted = round(sum(item["cost_usd"] for item in items), 9)
        rows.append({
            "eval_id": eval_id, "sample_id": sample_id,
            "cost_usd": accounted if complete else None,
            "partial_cost_usd": None if complete else accounted,
            "complete": complete,
            "generation_attempts": len(attempts), "expected_calls": len(attempts),
            "available_ids": len(sample_ids), "queried_ids": len(sample_ids),
            "billed_calls": len(own_ids & billed.keys()),
            "unknown_attempts": missing_ids + sum(generation_id not in billed for generation_id in attempts if generation_id),
            "lookup_failures": lookup_failures,
            "shared_generation_ids": len(shared_ids),
            "providers": sorted({item["provider"] for item in available_items if item["provider"]}),
            "routed_models": sorted({item["model"] for item in available_items if item["model"]}),
        })

    run_complete = bool(rows) and all(row["complete"] for row in rows)
    run_cost = round(sum(item["cost_usd"] for item in billed.values()), 9)
    result = {
        "rows": rows,
        "complete": run_complete,
        "cost_usd": run_cost if run_complete else None,
        "partial_cost_usd": None if run_complete else run_cost,
        "generation_attempts": sum(row["generation_attempts"] for row in rows),
        "available_ids": len(ids), "queried_ids": len(ids),
        "billed_calls": len(billed),
        "unknown_attempts": sum(row["unknown_attempts"] for row in rows),
        "lookup_failures": len(set(ids) - billed.keys()),
    }
    output = ROOT / "artifacts/inspect/openrouter-billing" / f"{args.run_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=f".{output.name}.", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            file.write(json.dumps(result, indent=2) + "\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Billing metadata: {len(billed)}/{result['generation_attempts']} model attempts across {len(rows)} samples", flush=True)
    return 0 if run_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
