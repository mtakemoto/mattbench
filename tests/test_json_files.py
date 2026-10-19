"""Atomic JSON publication shared by the worker, report, billing and HA timing."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import json_files
from scripts.json_files import write_json_atomic


class AtomicJsonTests(unittest.TestCase):
    def test_readers_see_old_or_new_file_never_a_partial_one(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "summary.json"
            destination.write_text('{"rows":["old"]}\n')
            entered, proceed = threading.Event(), threading.Event()
            original = json.dump

            def slow_dump(*args, **kwargs):
                entered.set()
                self.assertTrue(proceed.wait(5))
                return original(*args, **kwargs)

            with patch.object(json_files.json, "dump", side_effect=slow_dump):
                writer = threading.Thread(target=write_json_atomic, args=(destination, {"rows": ["new"]}))
                writer.start()
                self.assertTrue(entered.wait(5))
                for _ in range(200):
                    self.assertEqual(json.loads(destination.read_text()), {"rows": ["old"]})
                proceed.set()
                writer.join(5)
                self.assertFalse(writer.is_alive())
            self.assertEqual(json.loads(destination.read_text()), {"rows": ["new"]})

    def test_failed_replace_keeps_previous_file_and_removes_temporary(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "timing.json"
            destination.write_text(json.dumps({"status": "previous"}))
            with patch.object(Path, "replace", side_effect=OSError("publication stopped")):
                with self.assertRaises(OSError):
                    write_json_atomic(destination, {"status": "complete"})
            self.assertEqual(json.loads(destination.read_text()), {"status": "previous"})
            self.assertEqual(list(destination.parent.iterdir()), [destination])


if __name__ == "__main__":
    unittest.main()
