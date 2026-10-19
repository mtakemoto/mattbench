import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run-inspect-suite.py"
from scripts.execution_plan import build_plan, save_plan
SPEC = importlib.util.spec_from_file_location("inspect_suite_runner", SCRIPT)
suite = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(suite)


class InspectSuiteRunnerTests(unittest.TestCase):
    def test_spawn_error_is_recorded_and_later_cases_continue(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if len(calls) == 1:
                raise OSError("simulated unavailable child executable")
            return type("Result", (), {"returncode": 0})()

        with tempfile.TemporaryDirectory() as directory:
            progress = Path(directory) / "progress.json"
            plan_file = Path(directory) / "plan.json"
            save_plan(plan_file, build_plan(suite=True))
            argv = ["run-inspect-suite.py", "--source", "freetoken", "--model", "fixture-model",
                    "--base-url", "http://127.0.0.1:1919/v1", "--run-id", "20261011000000001",
                    "--max-calls", str(build_plan(suite=True).max_calls),
                    "--plan-file", str(plan_file),
                    "--progress-file", str(progress)]
            with patch.object(sys, "argv", argv), patch.object(suite, "run_bounded", side_effect=run):
                result = suite.main()
            state = json.loads(progress.read_text())

        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 3)
        self.assertIn("--base-url", calls[0])
        self.assertEqual([row["status"] for row in state["completedCases"]], ["failed", "complete", "complete"])
        self.assertEqual(state["completedCount"], state["totalCases"])

    def test_each_suite_entry_expects_only_its_own_samples(self):
        plan = build_plan(case_id="all", include_laptops=True)
        self.assertTrue(plan.laptop_cases)
        self.assertEqual(set(suite.expected_samples("smoke", "smoke", plan)), {case.id for case in plan.smoke_cases})
        self.assertEqual(set(suite.expected_samples("laptop", "laptop", plan)), {case.id for case in plan.laptop_cases})
        first_ha = plan.ha_cases[0].id
        self.assertEqual(dict(suite.expected_samples("ha", first_ha, plan)), {first_ha: 1})


if __name__ == "__main__":
    unittest.main()
