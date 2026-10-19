"""Frozen execution-plan rows, not mutable fixture bytes, define a selected smoke task."""

import unittest
from pathlib import Path
from unittest.mock import patch

from inspect_pilot import smoke
from scripts.execution_plan import SmokeCase


class FrozenSmokeTests(unittest.TestCase):
    def test_optional_plan_rows_ignore_later_fixture_changes(self):
        rows = (SmokeCase("frozen", "Pinned question?", "Pinned answer", "smoke"),)
        with patch("inspect_pilot.ROOT", Path("/nonexistent-disposable-fixture-directory")):
            task = smoke(rows=rows)
        self.assertEqual([sample.id for sample in task.dataset], ["frozen"])
        self.assertEqual(task.dataset[0].input, "Pinned question?")
        self.assertEqual(task.dataset[0].target, "Pinned answer")


if __name__ == "__main__":
    unittest.main()
