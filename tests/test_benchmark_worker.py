import importlib.util
import json
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


def job_record(identifier="20261011000000000001"):
    return {"id": identifier, "status": "running", "phase": "running", "pid": os.getpid(),
            "source": "compatible", "model": "offline", "variant": "base", "caseId": "smoke",
            "startedAt": "2026-10-11T00:00:00+00:00", "updatedAt": "2026-10-11T00:00:00+00:00",
            "completedCases": [], "completedCount": 0, "totalCases": 1, "message": "Running"}


class WorkerOwnershipTests(unittest.TestCase):
    def test_exporting_worker_survives_console_restart_and_holds_lock(self):
        context = multiprocessing.get_context("fork")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "web"
            lock = worker.acquire_lock(directory)
            job = job_record()
            worker.atomic_json(directory / "job.json", job)
            settings = {"runId": job["id"], "caseId": "smoke", "source": "compatible", "model": "offline",
                        "variant": "base", "maxCalls": 2, "baseUrl": "http://127.0.0.1:9/v1", "capUsd": None}
            worker.atomic_json(directory / f"{job['id']}.request.json", settings)
            entered_export, allow_completion = context.Event(), context.Event()
            ready_read, ready_write = os.pipe()
            summary = root / "artifacts/inspect/summary.json"
            def execute():
                def run(command, **kwargs):
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
                self.assertEqual(terminal["completedCount"], 1)
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
                worker.start_job({"source": "compatible", "model": "bad model", "caseId": "smoke", "maxCalls": 2}, directory)
            self.assertEqual(worker.read_job(directory), previous)

    def test_launch_requires_explicit_exact_call_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            previous = {**job_record(), "status": "complete", "phase": "complete"}
            worker.atomic_json(directory / "job.json", previous)
            request = {"source": "compatible", "model": "offline", "caseId": "smoke",
                       "baseUrl": "http://127.0.0.1:9999/v1", "variant": "base"}
            for ceiling in ({}, {"maxCalls": None}, {"maxCalls": True}, {"maxCalls": 1}):
                with self.subTest(ceiling=ceiling), self.assertRaises(ValueError):
                    worker.start_job({**request, **ceiling}, directory)
                self.assertEqual(worker.read_job(directory), previous)


class WorkerCommandTests(unittest.TestCase):
    def test_openrouter_cap_flag_travels_only_with_a_cap(self):
        settings = {"runId": "20261011000000000001", "caseId": "smoke", "source": "openrouter",
                    "model": "minimax/minimax-m3.1-flash:free", "variant": "base", "maxCalls": 2,
                    "baseUrl": "", "capUsd": None}
        with tempfile.TemporaryDirectory() as temporary:
            free_command, _ = worker.command(settings, Path(temporary))
            self.assertNotIn("--cap-usd", free_command)
            paid_command, _ = worker.command({**settings, "model": "z-ai/glm-5.3-flash", "capUsd": 20}, Path(temporary))
            self.assertIn("--cap-usd", paid_command)
            self.assertIn("20", paid_command)
