"""The Inspect hook that publishes live per-case progress."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import case_progress


def score(value, explanation=None, metadata=None):
    return SimpleNamespace(value=value, explanation=explanation, metadata=metadata or {})


class CaseProgressHookTests(unittest.TestCase):
    def run_hook(self, *events):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.cases.entry.json"
            with patch.dict("os.environ", {case_progress.CASE_PROGRESS_ENV: str(path)}):
                hook = case_progress.CaseProgressHooks()
                self.assertTrue(hook.enabled())
                for method, data in events:
                    asyncio.run(getattr(hook, method)(data))
            return json.loads(path.read_text())

    def test_start_then_end_records_outcome_truncation_and_calls(self):
        start = SimpleNamespace(summary=SimpleNamespace(id="case_a", metadata={"prompt_variant": "careful"}))
        end = SimpleNamespace(sample=SimpleNamespace(
            id="case_a", metadata={"prompt_variant": "careful"}, error=None,
            scores={"match": score("I", "Wrong answer")}, output=SimpleNamespace(stop_reason="max_tokens"),
            events=[SimpleNamespace(event="model"), SimpleNamespace(event="tool"), SimpleNamespace(event="model")]))
        records = self.run_hook(("on_sample_start", start), ("on_sample_end", end))
        self.assertEqual(records, {"careful/case_a": {"state": "fail", "truncated": True, "calls": 2,
                                                      "explanation": "Wrong answer"}})

    def test_review_pending_and_errors_are_not_passes(self):
        pending = SimpleNamespace(sample=SimpleNamespace(
            id="b", metadata={}, error=None, scores={"s": score("C", metadata={"semantic_review_required": True})},
            output=None, events=[]))
        broken = SimpleNamespace(sample=SimpleNamespace(id="c", metadata={}, error="boom", scores={}, output=None, events=[]))
        records = self.run_hook(("on_sample_end", pending), ("on_sample_end", broken))
        self.assertEqual((records["base/b"]["state"], records["base/c"]["state"]), ("unscored", "error"))

    def test_disabled_without_a_progress_file(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(case_progress.CaseProgressHooks().enabled())


if __name__ == "__main__":
    unittest.main()
