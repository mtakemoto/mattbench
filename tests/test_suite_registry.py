"""Suites are discovered, never wired in by hand.

These tests protect the rule in ``suites/__init__.py``: adding a suite means
adding one module (and its fixture) to ``suites/``. If a test here fails after
you add code, move the suite-specific logic into the suite's module instead
of naming the suite elsewhere.
"""

import ast
import json
import re
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import suites
from scripts.console_bridge import describe
from scripts.execution_plan import build_plan, load_plan, save_plan
from suites import RunTarget

ROOT = Path(__file__).resolve().parents[1]
FAKE_MODULE = textwrap.dedent('''
    from pathlib import Path
    from suites import Case, Suite, require_text

    class FakeSuite(Suite):
        id = "fake_suite"
        label = "Fake suite"
        description = "Discovered without editing any other file."
        fixture = "unused.json"

        def fixture_path(self):
            return Path(__file__).with_name("fake_suite.json")

        def parse_row(self, row):
            require_text(row, "prompt", self.id)
            return self.make_case(row, name=row["id"], max_model_calls=2)

        def task(self, cases, variant):
            raise NotImplementedError

    SUITE = FakeSuite()
''')


class SuiteDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        package = Path(self.directory.name)
        (package / "fake_suite.py").write_text(FAKE_MODULE)
        (package / "fake_suite.json").write_text(json.dumps([{"id": "fake_one", "prompt": "Q?"},
                                                             {"id": "fake_two", "prompt": "Q?"}]))
        self.path = patch.object(suites, "__path__", [*suites.__path__, str(package)])
        self.path.start()
        suites.registry.cache_clear()

    def tearDown(self):
        self.path.stop()
        suites.registry.cache_clear()
        sys.modules.pop("suites.fake_suite", None)
        self.directory.cleanup()

    def test_new_suite_module_reaches_catalog_plan_and_runner_without_other_edits(self):
        catalog = {suite["id"]: suite for suite in describe()["suites"]}
        self.assertEqual([case["id"] for case in catalog["fake_suite"]["cases"]], ["fake_one", "fake_two"])

        plan = build_plan()
        entry = plan.entry("fake_suite")
        self.assertEqual(entry.model_calls, 4)
        self.assertIn(entry, plan.entries)
        self.assertEqual(plan.max_calls, sum(case["maxModelCalls"] for suite in catalog.values() for case in suite["cases"]))
        self.assertEqual(build_plan(["fake_two"]).cases[0].id, "fake_two")

        command = entry.command(RunTarget("compatible", "m", "20261011010203", Path("plan.json")))
        self.assertEqual(command[command.index("--suite") + 1], "fake_suite")
        with tempfile.TemporaryDirectory() as directory:
            frozen = Path(directory) / "plan.json"
            save_plan(frozen, plan)
            self.assertEqual(load_plan(frozen), plan)


LEGACY_FILES = {
    "smoke.py",  # Promptfoo-era offline grader, kept as a historical baseline.
}


class NoHardCodedSuiteTests(unittest.TestCase):
    def test_suite_ids_appear_only_inside_the_suites_package(self):
        suite_ids = set(suites.registry())
        offenders = []
        for path in [*ROOT.glob("*.py"), *ROOT.glob("scripts/*.py")]:
            if path.name in LEGACY_FILES:
                continue
            for node in ast.walk(ast.parse(path.read_text(), str(path))):
                if isinstance(node, ast.Constant) and node.value in suite_ids:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.value!r}")
        quoted = re.compile(r"""['"`](%s)['"`]""" % "|".join(map(re.escape, suite_ids)))
        for path in (ROOT / "web/src").rglob("*"):
            if path.suffix in {".ts", ".svelte"}:
                for number, line in enumerate(path.read_text().splitlines(), 1):
                    if quoted.search(line):
                        offenders.append(f"{path.relative_to(ROOT)}:{number}")
        self.assertEqual(offenders, [], "Suite IDs must come from the registry; see suites/__init__.py.")


if __name__ == "__main__":
    unittest.main()
