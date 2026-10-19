"""Process lifetime checks use only short-lived local Python sleepers."""

import asyncio
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.bounded_process import run_bounded, run_bounded_async


class BoundedProcessTests(unittest.TestCase):
    def test_timeout_terminates_child_and_descendant_group(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "child.pid"
            source = (
                "import subprocess,sys,time; "
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "
                "open(sys.argv[1],'w').write(str(child.pid)); time.sleep(30)"
            )
            started = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded([sys.executable, "-c", source, str(pid_file)], timeout=0.3,
                            capture_output=True)
            self.assertLess(time.monotonic() - started, 4)
            self.assertTrue(pid_file.exists())
            # Init may reap the orphan before open (ENOENT) or during read (ESRCH).
            descendant = Path(f"/proc/{pid_file.read_text()}/stat")
            try:
                state = descendant.read_text().split()[2]
            except (FileNotFoundError, ProcessLookupError):
                state = "gone"
            self.assertIn(state, ("Z", "gone"))

    def test_result_and_check_semantics(self):
        result = run_bounded([sys.executable, "-c", "import sys; print('ok'); sys.exit(3)"],
                             timeout=2, capture_output=True)
        self.assertEqual((result.returncode, result.stdout.strip()), (3, "ok"))
        with self.assertRaises(subprocess.CalledProcessError):
            run_bounded([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=2, check=True)

    def test_async_cancellation_terminates_child(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as directory:
                marker = Path(directory) / "started"
                source = "import pathlib,sys,time; pathlib.Path(sys.argv[1]).touch(); time.sleep(30)"
                running = asyncio.create_task(run_bounded_async(
                    [sys.executable, "-c", source, str(marker)], timeout=30, capture_output=True))
                for _ in range(500):
                    if marker.exists():
                        break
                    await asyncio.sleep(0.01)
                try:
                    self.assertTrue(marker.exists())
                finally:
                    running.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await asyncio.wait_for(running, timeout=4)

        asyncio.run(scenario())

    def test_async_timeout_maps_to_subprocess_error(self):
        async def scenario():
            with self.assertRaises(subprocess.TimeoutExpired):
                await run_bounded_async([sys.executable, "-c", "import time; time.sleep(30)"],
                                        timeout=0.1, capture_output=True)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
