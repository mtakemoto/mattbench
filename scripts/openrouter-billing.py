"""Fetch exact billed costs for one finished OpenRouter run without storing request IDs."""

import argparse
import json
import os
import re
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
            if not isinstance(amount, (int, float)) or amount < 0:
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
    for kind in ("selected", "ha"):
        for path in (ROOT / "artifacts/inspect" / kind / args.run_id).glob("*.eval"):
            log = read_eval_log(path)
            for sample in log.samples or []:
                if not log.eval.model.startswith("openai-api/openrouter/"):
                    continue
                ids = [event.output.response_id for event in sample.events
                       if event.event == "model" and event.output and event.output.response_id]
                jobs.append((log.eval.eval_id, sample.id, ids))

    ids = sorted({generation_id for _, _, sample_ids in jobs for generation_id in sample_ids})
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {generation_id: pool.submit(generation, generation_id, key) for generation_id in ids}
        billed = {}
        for generation_id, future in futures.items():
            try:
                billed[generation_id] = future.result()
            except (ValueError, HTTPError, OSError, TimeoutError):
                pass

    rows = []
    for eval_id, sample_id, sample_ids in jobs:
        complete = bool(sample_ids) and all(generation_id in billed for generation_id in sample_ids)
        items = [billed[generation_id] for generation_id in sample_ids if generation_id in billed]
        rows.append({"eval_id": eval_id, "sample_id": sample_id,
                     "cost_usd": round(sum(item["cost_usd"] for item in items), 9) if complete else None,
                     "billed_calls": len(items), "expected_calls": len(sample_ids),
                     "providers": sorted({item["provider"] for item in items if item["provider"]}),
                     "routed_models": sorted({item["model"] for item in items if item["model"]})})

    output = ROOT / "artifacts/inspect/openrouter-billing" / f"{args.run_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"rows": rows}, indent=2) + "\n")
    print(f"Billing metadata: {sum(row['billed_calls'] for row in rows)}/{sum(row['expected_calls'] for row in rows)} model calls across {len(rows)} samples", flush=True)
    return 0 if all(row["cost_usd"] is not None for row in rows) and rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
