"""Offline regressions for frozen requests and bounded Inspect orchestration."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import suites
from scripts.console_bridge import describe
from scripts.execution_plan import build_plan, load_plan, require_calls, run_id, save_plan, validate_request
from scripts.run_inspect_settings import compatible_base, local_config, prepare_provider, read_env_file, validate_model
from suites.smoke import SUITE as SMOKE

ROOT = Path(__file__).resolve().parents[1]


def runner(filename):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExecutionPlanTests(unittest.TestCase):
    def fixture(self, directory, count):
        rows = [{"id": f"case_{index}", "prompt": f"Question {index}", "expected": "yes",
                 "category": "reasoning_smoke"} for index in range(count)]
        path = Path(directory) / "smoke.json"
        path.write_text(json.dumps(rows))
        return path

    def test_added_and_removed_fixtures_derive_single_and_comparison_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(directory, 3)
            for count in (3, 1):
                self.fixture(directory, count)
                for variants in (("base",), SMOKE.variants):
                    plan = build_plan([SMOKE.id], variants, fixture_paths={SMOKE.id: fixture})
                    multiplier = len(variants)
                    self.assertEqual(plan.max_calls, count * multiplier)
                    self.assertEqual(sum(entry.expected_samples.total() for entry in plan.entries), count * multiplier)
                    with self.assertRaisesRegex(ValueError, "requires exactly"):
                        require_calls(plan, plan.max_calls + 1)
                    frozen = Path(directory) / "plan.json"
                    save_plan(frozen, plan)
                    self.assertEqual(load_plan(frozen), plan)
            fixture.write_text("{malformed")
            self.assertEqual(load_plan(frozen).max_calls, 2)
            with self.assertRaisesRegex(ValueError, "Cannot read smoke fixture"):
                build_plan([SMOKE.id], fixture_paths={SMOKE.id: fixture})

    def test_plan_rejects_tampered_budget_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            save_plan(path, build_plan())
            data = json.loads(path.read_text())
            data["maxCalls"] += 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "model-call limits"):
                load_plan(path)
            path.write_text("{unclosed")
            with self.assertRaisesRegex(ValueError, "Invalid execution plan JSON"):
                load_plan(path)

    def test_default_run_id_and_bad_explicit_id(self):
        self.assertRegex(run_id(), r"^[0-9]{14,20}$")
        with self.assertRaisesRegex(ValueError, "Run ID"):
            run_id("20261011T010203")

    def test_quoted_local_config_and_colon_model_match_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text('MATTBENCH_LOCAL_BASE_URL="http://127.0.0.1:1111/v1"\n'
                                "MATTBENCH_LOCAL_MODEL='example:latest'\n")
            with patch("scripts.run_inspect_settings.ROOT", Path(directory)), patch.dict(
                    "os.environ", {"MATTBENCH_LOCAL_BASE_URL": "", "MATTBENCH_LOCAL_MODEL": ""}):
                self.assertEqual(local_config(), ("http://127.0.0.1:1111/v1", "example:latest"))
                self.assertEqual(read_env_file()["MATTBENCH_LOCAL_MODEL"], "example:latest")
            self.assertEqual(validate_model("example:latest"), "example:latest")
            with self.assertRaisesRegex(ValueError, "loopback"):
                compatible_base("http://10.0.0.2/v1", loopback_only=True)

    def test_bridge_describes_every_suite_and_its_call_ceiling(self):
        catalog = describe()
        self.assertEqual([suite["id"] for suite in catalog["suites"]], list(suites.registry()))
        self.assertEqual(sum(case["maxModelCalls"] for suite in catalog["suites"] for case in suite["cases"]),
                         build_plan().max_calls)
        self.assertNotIn("API_KEY", json.dumps(catalog))

    def test_selection_accepts_all_suites_and_case_ids_and_rejects_unknown_ids(self):
        every = build_plan()
        self.assertEqual({case.suite for case in every.cases}, set(suites.registry()))
        first_suite, first_case = every.cases[0].suite, every.cases[-1]
        mixed = build_plan([first_suite, first_case.id])
        self.assertIn(first_case, mixed.cases)
        self.assertEqual(build_plan([first_suite, first_suite]).cases, build_plan([first_suite]).cases)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            build_plan(["no_such_suite_or_case"])

    def test_variants_must_be_supported_by_every_selected_suite(self):
        single_variant = next(suite for suite in suites.registry().values() if suite.variants == ("base",))
        with self.assertRaisesRegex(ValueError, "does not support"):
            build_plan([single_variant.id], ("base", "careful"))

    def test_request_returns_secret_free_settings_and_requires_cap_for_paid_models(self):
        settings, plan = validate_request({"source": "freetoken", "model": "example:latest", "selection": [SMOKE.id],
                                           "baseUrl": "http://127.0.0.1:1111/v1", "runId": "20261011010203"})
        self.assertEqual(settings["maxCalls"], len(plan.cases))
        self.assertNotIn("API_KEY", json.dumps(settings))
        with self.assertRaisesRegex(ValueError, "Confirm"):
            validate_request({"source": "openrouter", "model": "z-ai/glm-5.3-flash", "capUsd": 20})
        alias = "~z-ai/glm-flash-latest"
        paid, _ = validate_request({"source": "openrouter", "model": alias, "selection": [SMOKE.id],
                                    "capUsd": 20, "capConfirmed": True, "runId": "20261011010203"})
        self.assertEqual(paid["model"], alias)
        with self.assertRaisesRegex(ValueError, "Unknown settings fields"):
            validate_request({"source": "freetoken", "model": "test", "baseUrl": "http://localhost/v1",
                              "secret": "not-printed"})

    def test_free_openrouter_models_skip_the_paid_cap_gate(self):
        free, _ = validate_request({"source": "openrouter", "model": "minimax/minimax-m3.1-flash:free",
                                    "selection": [SMOKE.id], "runId": "20261011010203"})
        self.assertIsNone(free["capUsd"])
        capped, _ = validate_request({"source": "openrouter", "model": "minimax/minimax-m3.1-flash:free",
                                      "selection": [SMOKE.id], "capUsd": 20, "capConfirmed": False,
                                      "runId": "20261011010203"})
        self.assertEqual(capped["capUsd"], 20)
        with self.assertRaisesRegex(ValueError, "before a paid run"):
            validate_request({"source": "openrouter", "model": "z-ai/glm-5.3-flash", "selection": [SMOKE.id],
                              "capUsd": 20, "runId": "20261011010203"})
        with self.assertRaisesRegex(ValueError, r"between \$0 and \$20"):
            validate_request({"source": "openrouter", "model": "minimax/minimax-m3.1-flash:free",
                              "selection": [SMOKE.id], "capUsd": 25, "runId": "20261011010203"})

    def test_provider_requires_cap_only_for_paid_openrouter_models(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            self.assertEqual(prepare_provider("openrouter", "minimax/minimax-m3.1-flash:free"),
                             "openai-api/openrouter/minimax/minimax-m3.1-flash:free")
            with self.assertRaisesRegex(ValueError, r"between \$0 and \$20"):
                prepare_provider("openrouter", "z-ai/glm-5.3-flash")
            self.assertEqual(prepare_provider("openrouter", "z-ai/glm-5.3-flash", cap_usd=20),
                             "openai-api/openrouter/z-ai/glm-5.3-flash")


    def test_real_inspect_offline_provider_error_never_retries_attempt(self):
        from inspect_ai import eval_set

        with tempfile.TemporaryDirectory() as directory:
            plan = build_plan([SMOKE.id], fixture_paths={SMOKE.id: self.fixture(directory, 2)})
            attempts = []

            def failing_provider(input, tools, tool_choice, config):
                attempts.append(input[-1].content)
                raise RuntimeError("offline simulated provider failure")

            success, _logs = eval_set(
                tasks=[SMOKE.task(plan.cases, "base")], model="mockllm/model",
                model_args={"custom_outputs": failing_provider}, max_retries=0, retry_attempts=0,
                max_samples=1, max_tasks=1, log_dir=str(Path(directory) / "logs"), display="none",
            )
            self.assertFalse(success)
            self.assertGreater(len(attempts), 0)
            self.assertLessEqual(len(attempts), plan.max_calls)

    def case_runner_argv(self, directory, max_calls):
        plan_file = Path(directory) / "plan.json"
        save_plan(plan_file, build_plan([SMOKE.id]))
        return ["run-inspect-cases.py", "--suite", SMOKE.id, "--plan-file", str(plan_file),
                "--source", "freetoken", "--model", "test:latest", "--base-url", "http://127.0.0.1:1111/v1",
                "--max-calls", str(max_calls)]

    def test_case_runner_omitted_run_id_reaches_endpoint_validation(self):
        cases = runner("run-inspect-cases.py")
        with tempfile.TemporaryDirectory() as directory:
            argv = self.case_runner_argv(directory, build_plan([SMOKE.id]).max_calls)
            with patch.object(sys, "argv", argv), patch.object(cases, "prepare_provider",
                                                              side_effect=ValueError("offline endpoint probe")) as provider:
                with self.assertRaises(SystemExit) as error:
                    cases.main()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(provider.call_count, 1)

    def test_case_runner_bad_budget_stops_before_endpoint_discovery(self):
        cases = runner("run-inspect-cases.py")
        with tempfile.TemporaryDirectory() as directory:
            argv = self.case_runner_argv(directory, 999)
            with patch.object(sys, "argv", argv), patch.object(cases, "prepare_provider") as provider:
                with self.assertRaises(SystemExit):
                    cases.main()
        provider.assert_not_called()

    def test_suite_wrong_whole_cap_rejects_before_child(self):
        suite = runner("run-inspect-suite.py")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            save_plan(path, build_plan())
            argv = ["run-inspect-suite.py", "--source", "compatible", "--model", "example:latest",
                    "--base-url", "http://127.0.0.1:1111/v1", "--run-id", "20261011010203",
                    "--progress-file", str(Path(directory) / "progress.json"),
                    "--max-calls", "2", "--plan-file", str(path)]
            with patch.object(sys, "argv", argv), patch.object(suite, "run_bounded") as child:
                with self.assertRaises(SystemExit):
                    suite.main()
                child.assert_not_called()

    def test_corrupt_score_reports_unavailable_and_suite_continues(self):
        suite = runner("run-inspect-suite.py")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            plan = build_plan()
            plan_file = directory / "plan.json"
            save_plan(plan_file, plan)
            log_dir = directory / plan.entries[0].suite.id / "20261011010203"
            log_dir.mkdir(parents=True)
            (log_dir / "corrupt.eval").write_text("{damaged")
            commands = []

            def fake_run(command, **_kwargs):
                commands.append(command)
                return SimpleNamespace(returncode=0)

            argv = ["run-inspect-suite.py", "--source", "compatible", "--model", "model:latest",
                    "--base-url", "http://127.0.0.1:1111/v1", "--run-id", "20261011010203",
                    "--progress-file", str(directory / "progress.json"), "--max-calls", str(plan.max_calls),
                    "--plan-file", str(plan_file)]
            with patch.object(suites, "INSPECT_LOG_ROOT", directory), patch.object(sys, "argv", argv), \
                    patch.object(suite, "read_eval_log", side_effect=ValueError("damaged score")), \
                    patch.object(suite, "run_bounded", side_effect=fake_run):
                self.assertEqual(suite.main(), 0)
            progress = json.loads((directory / "progress.json").read_text())
            self.assertEqual(len(commands), len(plan.entries))
            self.assertIn("Score unavailable", progress["completedCases"][0]["scoreUnavailable"])
            self.assertTrue(all(row["status"] == "complete" for row in progress["completedCases"]))


if __name__ == "__main__":
    unittest.main()
