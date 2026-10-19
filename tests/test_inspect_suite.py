"""Focused orchestration checks for the console's run-all suite."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run-inspect-suite.py"
SPEC = importlib.util.spec_from_file_location("run_inspect_suite", MODULE_PATH)
assert SPEC and SPEC.loader
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)
from scripts.execution_plan import build_plan, save_plan
from suites import RunTarget


class InspectSuiteTests(unittest.TestCase):
    def test_runs_every_entry_in_order_and_keeps_progress_after_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            progress_file = Path(temp) / "progress.json"
            plan_file = Path(temp) / "plan.json"
            plan = build_plan()
            save_plan(plan_file, plan)
            entries = [entry.id for entry in plan.entries]
            commands = []
            snapshots = []

            def fake_run(command, **_kwargs):
                commands.append(command)
                snapshots.append(json.loads(progress_file.read_text()))
                # Fail the second entry and confirm that later entries still launch.
                return SimpleNamespace(returncode=1 if len(commands) == 2 else 0)

            argv = [
                "run-inspect-suite.py", "--source", "compatible", "--model", "example-model",
                "--base-url", "http://127.0.0.1:11434/v1", "--run-id", "20261011010203",
                "--progress-file", str(progress_file), "--max-calls", str(plan.max_calls),
                "--plan-file", str(plan_file),
            ]
            with patch.object(sys, "argv", argv), patch.object(suite, "run_bounded", side_effect=fake_run), \
                    patch.object(suite, "entry_score", return_value=(True, 1, None)):
                result = suite.main()
            final = json.loads(progress_file.read_text())

        self.assertEqual(result, 1)
        self.assertEqual(len(commands), len(entries))
        self.assertEqual([snapshot["currentCaseId"] for snapshot in snapshots], entries)
        self.assertEqual(snapshots[2]["completedCases"][1], {"caseId": entries[1], "status": "failed",
                                                             "message": snapshots[2]["completedCases"][1]["message"]})
        self.assertEqual(final["phase"], "exporting")
        self.assertIsNone(final["currentCaseId"])
        self.assertEqual(final["completedCount"], final["totalCases"])
        self.assertEqual([item["status"] for item in final["completedCases"]],
                         ["complete", "failed", *["complete"] * (len(entries) - 2)])

    def test_each_entry_command_targets_its_own_suite_and_cases(self):
        plan = build_plan()
        target = RunTarget("compatible", "example-model", "20261011010203", Path("plan.json"), "http://127.0.0.1:1/v1")
        for entry in plan.entries:
            with self.subTest(entry=entry.id):
                command = entry.command(target)
                self.assertEqual(command[command.index("--max-calls") + 1], str(entry.model_calls))
                if "--case" in command:
                    cases = [command[index + 1] for index, value in enumerate(command) if value == "--case"]
                    self.assertEqual(cases, [case.id for case in entry.cases])

    def test_spawn_error_is_recorded_and_later_entries_continue(self):
        calls = []

        def run(command, **_kwargs):
            calls.append(command)
            if len(calls) == 1:
                raise OSError("simulated unavailable child executable")
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as directory:
            progress = Path(directory) / "progress.json"
            plan_file = Path(directory) / "plan.json"
            plan = build_plan()
            save_plan(plan_file, plan)
            argv = ["run-inspect-suite.py", "--source", "freetoken", "--model", "fixture-model",
                    "--base-url", "http://127.0.0.1:1919/v1", "--run-id", "20261011000000001",
                    "--max-calls", str(plan.max_calls), "--plan-file", str(plan_file), "--progress-file", str(progress)]
            with patch.object(sys, "argv", argv), patch.object(suite, "run_bounded", side_effect=run), \
                    patch.object(suite, "entry_score", return_value=(True, 1, None)):
                result = suite.main()
            state = json.loads(progress.read_text())

        self.assertEqual(result, 1)
        self.assertEqual(len(calls), len(plan.entries))
        self.assertIn("--base-url", calls[0])
        self.assertEqual([row["status"] for row in state["completedCases"]],
                         ["failed", *["complete"] * (len(plan.entries) - 1)])
        self.assertIn("could not start", state["completedCases"][0]["message"])

    def test_each_entry_expects_one_sample_per_case_and_variant(self):
        for entry in build_plan().entries:
            with self.subTest(entry=entry.id):
                self.assertEqual(set(entry.expected_samples), {case.id for case in entry.cases})
                self.assertEqual(entry.expected_samples.total(), len(entry.cases) * len(entry.variants))


if __name__ == "__main__":
    unittest.main()
