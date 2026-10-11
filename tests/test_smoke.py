"""Check the pinned smoke grader without calling any provider."""

import json
import unittest
from pathlib import Path

from smoke import grade


TASKS = json.loads(
    (Path(__file__).resolve().parents[1] / "tasks" / "smoke.json").read_text(
        encoding="utf-8"
    )
)


class SmokeGradingTests(unittest.TestCase):
    def test_pinned_answers_pass(self):
        self.assertEqual(
            grade(TASKS, {"strawberry_r_count": "3\n", "car_wash_transport": "drive"}),
            {"strawberry_r_count": True, "car_wash_transport": True},
        )

    def test_wrong_or_missing_answers_fail(self):
        self.assertEqual(
            grade(TASKS, {"strawberry_r_count": "2"}),
            {"strawberry_r_count": False, "car_wash_transport": False},
        )


if __name__ == "__main__":
    unittest.main()
