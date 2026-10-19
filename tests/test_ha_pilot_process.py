"""The HA lifecycle tests never contact Docker, a model, or Home Assistant."""

import importlib.util
import io
import signal
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run-inspect-ha-pilot.py"
SPEC = importlib.util.spec_from_file_location("ha_pilot_process", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pilot)


class HaPilotProcessTests(unittest.TestCase):
    def test_progress_failure_does_not_skip_cleanup_or_mask_startup_error(self):
        calls = []

        def docker(command, **_kwargs):
            calls.append(command)
            if command[1:3] == ["rm", "-f"] and "mattbench-mcp" in command[3]:
                raise OSError("private service diagnostic must not be printed")
            return subprocess.CompletedProcess(command, 0, "", "")

        def fail_progress(_path, _case, message, _phase="running"):
            if message.startswith("Cleaning up"):
                raise OSError("private progress location must not be printed")

        argv = [str(SCRIPT), "--preflight-only", "--run-id", "20261011000000001",
                "--progress-file", "/not/a/real/progress.json"]
        stderr = io.StringIO()
        with patch.object(sys, "argv", argv), patch.object(sys, "stderr", stderr), \
             patch.object(pilot, "install_synthetic_component"), \
             patch.object(pilot, "wait_http", side_effect=RuntimeError("original setup failure")), \
             patch.object(pilot, "progress", side_effect=fail_progress), \
             patch.object(pilot, "run_bounded", side_effect=docker), \
             patch.object(pilot, "write_json_atomic") as publish:
            with self.assertRaisesRegex(RuntimeError, "original setup failure"):
                pilot.main()
        self.assertTrue(any(cmd[1:3] == ["network", "create"] for cmd in calls))
        self.assertTrue(any(cmd[1] == "run" for cmd in calls))
        self.assertEqual([cmd[1] for cmd in calls[-4:]], ["exec", "rm", "rm", "network"])
        self.assertEqual(publish.call_args.args[1]["status"], "failed")
        self.assertIn("Remove MCP container: OSError", stderr.getvalue())
        self.assertNotIn("private", stderr.getvalue())

    def test_sigterm_requests_cleanup_before_worker_exits(self):
        calls = []

        def run(command, **_kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        argv = [str(SCRIPT), "--preflight-only", "--run-id", "20261011000000001"]
        with patch.object(sys, "argv", argv), patch.object(pilot, "install_synthetic_component"), \
             patch.object(pilot, "progress"), patch.object(pilot, "write_json_atomic") as publish, \
             patch.object(pilot, "run_bounded", side_effect=run), \
             patch.object(pilot, "wait_http", side_effect=lambda *_: signal.raise_signal(signal.SIGTERM)):
            with self.assertRaises(pilot.WorkerInterrupted):
                pilot.main()
        self.assertEqual([cmd[1] for cmd in calls[-4:]], ["exec", "rm", "rm", "network"])
        self.assertEqual(publish.call_args.args[1]["status"], "failed")

    def test_mismatched_confirmed_calls_fail_before_docker(self):
        argv = [str(SCRIPT), "--preflight-only", "--max-calls", "1"]
        with patch.object(sys, "argv", argv), patch.object(pilot, "run_bounded") as run, \
             patch.object(sys, "stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                pilot.main()
        self.assertEqual(error.exception.code, 2)
        run.assert_not_called()

    def test_cleanup_attempts_all_owned_resources_after_independent_failures(self):
        calls = []

        def run(command, **_kwargs):
            calls.append(command)
            if command[1] == "exec":
                return subprocess.CompletedProcess(command, 9, "", "private service output")
            if command[1] == "rm" and command[-1] == "ha":
                raise subprocess.TimeoutExpired(command, 0.1)
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch.object(pilot, "run_bounded", side_effect=run):
            errors = pilot.cleanup_resources("mcp", "ha", "net")
        self.assertEqual([cmd[1] for cmd in calls], ["exec", "rm", "rm", "network"])
        self.assertEqual(errors, ["Restore HA config ownership: exit 9", "Remove HA container: TimeoutExpired"])
        self.assertTrue(all("private" not in error for error in errors))

    def test_timing_write_failure_does_not_replace_setup_failure(self):
        argv = [str(SCRIPT), "--preflight-only", "--run-id", "20261011000000001"]
        result = lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "", "")
        with patch.object(sys, "argv", argv), patch.object(pilot, "progress"), \
             patch.object(pilot, "install_synthetic_component", side_effect=RuntimeError("setup failed")), \
             patch.object(pilot, "run_bounded", side_effect=result), \
             patch.object(pilot, "write_json_atomic", side_effect=OSError("timing cannot publish")), \
             patch.object(sys, "stderr", io.StringIO()) as errors:
            with self.assertRaisesRegex(RuntimeError, "setup failed"):
                pilot.main()
        self.assertIn("HA timing publication failed (OSError)", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
