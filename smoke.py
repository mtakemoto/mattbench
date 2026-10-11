"""Offline grader for the two no-tool smoke cases.

Usage: python3 smoke.py /path/to/responses.json
Responses must be a JSON object mapping task IDs to answer strings.
This script never calls a model or a Home Assistant server.
"""

import json
import sys
from pathlib import Path


TASKS_PATH = Path(__file__).parent / "tasks" / "smoke.json"


def grade(tasks: list[dict[str, str]], responses: dict[str, str]) -> dict[str, bool]:
    """Return one exact-answer result per pinned smoke case."""
    results = {}
    for task in tasks:
        answer = responses.get(task["id"])
        results[task["id"]] = (
            isinstance(answer, str)
            and answer.strip().casefold() == task["expected"].casefold()
        )
    return results


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 smoke.py /path/to/responses.json", file=sys.stderr)
        return 2

    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    responses = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if not isinstance(responses, dict):
        print("Responses must be a JSON object", file=sys.stderr)
        return 2

    results = grade(tasks, responses)
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
