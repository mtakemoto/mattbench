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


class InspectSuiteTests(unittest.TestCase):
    def test_runs_smoke_then_each_ha_case_and_keeps_progress_after_failure(self):
        manifest = json.loads((ROOT / "tasks/inspect-ha-cases.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            progress_file = Path(temp) / "progress.json"
            commands = []
            snapshots = []

            def fake_run(command, **_kwargs):
                commands.append(command)
                snapshots.append(json.loads(progress_file.read_text()))
                # Fail the first HA run and confirm that the next case still launches.
                return SimpleNamespace(returncode=1 if len(commands) == 2 else 0)

            argv = [
                "run-inspect-suite.py", "--source", "compatible", "--model", "example-model",
                "--base-url", "http://127.0.0.1:11434/v1", "--run-id", "20261011010203",
                "--progress-file", str(progress_file),
            ]
            with patch.object(sys, "argv", argv), patch.object(suite.subprocess, "run", side_effect=fake_run):
                result = suite.main()

            self.assertEqual(result, 1)
            self.assertEqual(len(commands), 1 + len(manifest))
            self.assertIn("run-inspect-selected.py", commands[0][1])
            self.assertIn("--variant", commands[0])
            self.assertIn("base", commands[0])
            self.assertIn("--base-url", commands[0])
            self.assertIn("http://127.0.0.1:11434/v1", commands[0])
            ha_commands = commands[1:]
            self.assertEqual(
                [command[command.index("--case") + 1] for command in ha_commands],
                [row["id"] for row in manifest],
            )

            first_ha = manifest[0]["id"]
            second_ha = manifest[1]["id"]
            self.assertEqual(snapshots[0]["currentCaseId"], "smoke")
            self.assertEqual(snapshots[1]["completedCases"], [{"caseId": "smoke", "status": "complete", "message": None}])
            self.assertEqual(snapshots[2]["currentCaseId"], second_ha)
            self.assertEqual(snapshots[2]["completedCases"][1]["caseId"], first_ha)
            self.assertEqual(snapshots[2]["completedCases"][1]["status"], "failed")
            final = json.loads(progress_file.read_text())
            self.assertEqual(final["phase"], "exporting")
            self.assertIsNone(final["currentCaseId"])
            self.assertEqual(final["completedCount"], final["totalCases"])
            self.assertEqual([item["status"] for item in final["completedCases"]], ["complete", "failed", "complete"])

    def test_openrouter_passes_cap_to_every_child_without_local_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            argv = [
                "run-inspect-suite.py", "--source", "openrouter", "--model", "z-ai/glm-5.3-flash",
                "--cap-usd", "20", "--run-id", "20261011010203",
                "--progress-file", str(Path(temp) / "progress.json"),
            ]
            with patch.object(sys, "argv", argv), patch.dict(suite.os.environ, {"OPENROUTER_API_KEY": "test-only"}), patch.object(suite.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
                self.assertEqual(suite.main(), 0)
            self.assertEqual(run.call_count, 1 + len(json.loads((ROOT / "tasks/inspect-ha-cases.json").read_text())))
            for call in run.call_args_list:
                command = call.args[0]
                self.assertEqual(command[command.index("--cap-usd") + 1], "20.0")
                self.assertNotIn("--base-url", command)


if __name__ == "__main__":
    unittest.main()
