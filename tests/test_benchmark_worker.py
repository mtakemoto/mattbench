import importlib.util
import multiprocessing
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("benchmark_worker", ROOT / "scripts/benchmark-worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
from scripts.execution_plan import build_plan, save_plan
from suites import registry

FIRST_SUITE = next(iter(registry()))


def job_record(identifier="20261011000000000001"):
    return {"id": identifier, "status": "running", "phase": "running", "pid": os.getpid(),
            "source": "compatible", "model": "offline", "variants": ["base"], "selection": [FIRST_SUITE],
            "startedAt": "2026-10-11T00:00:00+00:00", "updatedAt": "2026-10-11T00:00:00+00:00",
            "completedEntries": [], "totalEntries": 1, "message": "Running"}


class WorkerOwnershipTests(unittest.TestCase):
    def test_exporting_worker_survives_console_restart_and_holds_lock(self):
        context = multiprocessing.get_context("fork")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "web"
            lock = worker.acquire_lock(directory)
            job = job_record()
            worker.atomic_json(directory / "job.json", job)
            plan = build_plan([FIRST_SUITE])
            settings = {"runId": job["id"], "selection": [FIRST_SUITE], "source": "compatible", "model": "offline",
                        "variants": ["base"], "maxCalls": plan.max_calls, "baseUrl": "http://127.0.0.1:9/v1", "capUsd": None}
            worker.atomic_json(directory / f"{job['id']}.request.json", settings)
            save_plan(directory / f"{job['id']}.plan.json", plan)
            entered_export, allow_completion = context.Event(), context.Event()
            ready_read, ready_write = os.pipe()
            summary = root / "artifacts/inspect/summary.json"
            def execute():
                def run(command, **kwargs):
                    if "run-inspect-suite.py" in command[1]:
                        worker.atomic_json(directory / f"{job['id']}.progress.json", {
                            "completedEntries": [{"entryId": FIRST_SUITE, "status": "complete"}],
                            "totalEntries": 1})
                    if "inspect-report.py" in command[1]:
                        entered_export.set()
                        if not allow_completion.wait(5):
                            raise RuntimeError("Test failed to release export")
                        worker.atomic_json(summary, {"schema_version": 1, "rows": [], "warnings": []})
                    return subprocess.CompletedProcess(command, 0)
                with patch.object(worker, "ROOT", root), patch.object(worker, "run_bounded", run):
                    worker.work(job["id"], directory, lock.fileno(), ready_read)
            child = context.Process(target=execute)
            child.start()
            os.close(ready_read)
            os.write(ready_write, b"1")
            os.close(ready_write)
            lock.close()
            try:
                self.assertTrue(entered_export.wait(5))
                # A fresh console observer sees an arbitrarily old exporting job as running.
                observed = worker.reconcile(directory)
                self.assertEqual((observed["status"], observed["phase"]), ("running", "exporting"))
                with self.assertRaisesRegex(ValueError, "already running"):
                    worker.start_job({}, directory)
                allow_completion.set()
                child.join(5)
                self.assertEqual(child.exitcode, 0)
                terminal = worker.reconcile(directory)
                self.assertEqual((terminal["status"], terminal["phase"]), ("complete", "complete"))
                self.assertEqual(len(terminal["completedEntries"]), 1)
            finally:
                allow_completion.set()
                if child.is_alive():
                    child.terminate()
                    child.join(5)

    def test_old_completion_cannot_overwrite_new_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            newer = job_record("20261011000000000002")
            worker.atomic_json(directory / "job.json", newer)
            with self.assertRaisesRegex(RuntimeError, "ownership changed"):
                worker.update_job(directory, "20261011000000000001", status="complete")
            self.assertEqual(worker.read_job(directory), newer)

    def test_dead_worker_is_reconciled_without_age_threshold(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            worker.atomic_json(directory / "job.json", job_record())
            self.assertEqual(worker.reconcile(directory)["status"], "interrupted")

    def test_invalid_request_does_not_replace_previous_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            previous = {**job_record(), "status": "complete", "phase": "complete"}
            worker.atomic_json(directory / "job.json", previous)
            with self.assertRaises(ValueError):
                worker.start_job({"source": "compatible", "model": "bad model", "selection": [FIRST_SUITE], "maxCalls": 2}, directory)
            self.assertEqual(worker.read_job(directory), previous)

    def test_launch_requires_explicit_exact_call_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            previous = {**job_record(), "status": "complete", "phase": "complete"}
            worker.atomic_json(directory / "job.json", previous)
            request = {"source": "compatible", "model": "offline", "selection": [FIRST_SUITE],
                       "baseUrl": "http://127.0.0.1:9999/v1", "variants": ["base"]}
            for ceiling in ({}, {"maxCalls": None}, {"maxCalls": True}, {"maxCalls": 1}):
                with self.subTest(ceiling=ceiling), self.assertRaises(ValueError):
                    worker.start_job({**request, **ceiling}, directory)
                self.assertEqual(worker.read_job(directory), previous)


class WorkerCommandTests(unittest.TestCase):
    def test_legacy_single_selection_job_is_normalized(self):
        legacy = {**job_record(), "status": "complete", "phase": "complete", "caseId": "all", "variant": "both",
                  "completedCases": [{"caseId": "smoke", "status": "complete"}], "completedCount": 1, "totalCases": 4}
        for field in ("selection", "variants", "completedEntries", "totalEntries"):
            del legacy[field]
        with tempfile.TemporaryDirectory() as temporary:
            worker.atomic_json(Path(temporary) / "job.json", legacy)
            job = worker.read_job(Path(temporary))
        self.assertEqual((job["selection"], job["variants"]), (["all"], ["base", "careful"]))
        self.assertEqual((job["completedEntries"], job["totalEntries"]), ([{"status": "complete", "entryId": "smoke"}], 4))

    def test_every_selection_runs_through_the_suite_orchestrator_with_plan_deadline(self):
        plan = build_plan()
        settings = {"runId": "20261011000000000001", "source": "compatible", "model": "offline",
                    "maxCalls": plan.max_calls, "baseUrl": "http://127.0.0.1:9/v1", "capUsd": None}
        with tempfile.TemporaryDirectory() as temporary:
            save_plan(Path(temporary) / f"{settings['runId']}.plan.json", plan)
            command, deadline = worker.command(settings, Path(temporary))
        self.assertTrue(command[1].endswith("run-inspect-suite.py"))
        self.assertEqual(deadline, plan.deadline_seconds)

    def test_openrouter_cap_flag_travels_only_with_a_cap(self):
        settings = {"runId": "20261011000000000001", "source": "openrouter",
                    "model": "minimax/minimax-m3.1-flash:free", "maxCalls": 2,
                    "baseUrl": "", "capUsd": None}
        with tempfile.TemporaryDirectory() as temporary:
            save_plan(Path(temporary) / f"{settings['runId']}.plan.json", build_plan([FIRST_SUITE]))
            free_command, _ = worker.command(settings, Path(temporary))
            self.assertNotIn("--cap-usd", free_command)
            paid_command, _ = worker.command({**settings, "model": "z-ai/glm-5.3-flash", "capUsd": 20}, Path(temporary))
            self.assertIn("--cap-usd", paid_command)
            self.assertIn("20", paid_command)


class LiveStatusTests(unittest.TestCase):
    def test_started_job_lists_every_queued_case(self):
        plan = build_plan([FIRST_SUITE])
        with tempfile.TemporaryDirectory() as temporary, patch.object(worker.subprocess, "Popen") as popen:
            popen.return_value.pid = os.getpid()
            job = worker.start_job({"source": "compatible", "model": "offline", "selection": [FIRST_SUITE],
                                    "baseUrl": "http://127.0.0.1:9/v1", "maxCalls": plan.max_calls}, Path(temporary))
        self.assertEqual([case["state"] for case in job["cases"]], ["queued"] * len(plan.cases))

    def write_running_job(self, directory, plan):
        job = job_record()
        worker.atomic_json(directory / "job.json", job)
        save_plan(directory / f"{job['id']}.plan.json", plan)
        return job

    def test_cases_merge_hook_records_and_mark_failed_entries_as_errors(self):
        plan = build_plan()
        first, second = plan.entries[0], plan.entries[1]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            job = self.write_running_job(directory, plan)
            worker.atomic_json(directory / f"{job['id']}.cases.{first.id}.json", {
                f"base/{first.cases[0].id}": {"state": "pass", "calls": 1},
                f"base/{first.cases[-1].id}": {"state": "running"}})
            worker.atomic_json(directory / f"{job['id']}.progress.json", {
                "completedEntries": [{"entryId": second.id, "status": "failed"}], "totalEntries": len(plan.entries)})
            lock = worker.acquire_lock(directory)  # a live worker holds the lock
            try:
                cases = {case["id"]: case for case in worker.status(directory)["cases"]}
            finally:
                lock.close()
            self.assertEqual(len(cases), len(plan.cases))
            self.assertEqual((cases[first.cases[0].id]["state"], cases[first.cases[0].id]["calls"]), ("pass", 1))
            if len(first.cases) > 1:
                self.assertEqual(cases[first.cases[-1].id]["state"], "running")
            self.assertTrue(all(cases[case.id]["state"] == "error" for case in second.cases))
            self.assertTrue(all(cases[case.id]["state"] == "queued" for case in plan.entries[-1].cases))

            # Once the worker is gone, unfinished cases are reported as not run.
            finished = worker.status(directory)
            self.assertEqual(finished["status"], "interrupted")
            self.assertIn("not_run", {case["state"] for case in finished["cases"]})

    def test_cancel_signals_only_a_live_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(ValueError, "No benchmark is running"):
                worker.cancel(directory)
            job = self.write_running_job(directory, build_plan([FIRST_SUITE]))
            lock = worker.acquire_lock(directory)
            try:
                with patch.object(worker.os, "killpg") as kill:
                    worker.cancel(directory)
                kill.assert_called_once_with(job["pid"], worker.signal.SIGTERM)
                self.assertTrue((directory / f"{job['id']}.cancel").exists())
            finally:
                lock.close()
            with patch.object(worker.os, "killpg") as kill:
                self.assertEqual(worker.cancel(directory)["status"], "interrupted")
            kill.assert_not_called()

    def test_cancelled_run_still_exports_finished_cases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "web"
            plan = build_plan([FIRST_SUITE])
            job = self.write_running_job(directory, plan)
            worker.atomic_json(directory / f"{job['id']}.request.json", {
                "runId": job["id"], "source": "compatible", "model": "offline", "maxCalls": plan.max_calls,
                "baseUrl": "http://127.0.0.1:9/v1", "capUsd": None})
            (directory / f"{job['id']}.cancel").touch()
            commands = []

            def run(command, **_kwargs):
                commands.append(command[1])
                if command[1].endswith("run-inspect-suite.py"):
                    raise KeyboardInterrupt
                worker.atomic_json(root / "artifacts/inspect/summary.json", {"rows": [], "warnings": []})
                return subprocess.CompletedProcess(command, 0)

            ready_read, ready_write = os.pipe()
            os.write(ready_write, b"1")
            os.close(ready_write)
            lock = worker.acquire_lock(directory)
            with patch.object(worker, "ROOT", root), patch.object(worker, "run_bounded", run), \
                    patch.object(worker.signal, "signal"):
                self.assertEqual(worker.work(job["id"], directory, os.dup(lock.fileno()), ready_read), 1)
            lock.close()
            final = worker.read_job(directory)
        self.assertTrue(commands[-1].endswith("inspect-report.py"))
        self.assertEqual(final["status"], "interrupted")
        self.assertIn("cancelled", final["message"])
