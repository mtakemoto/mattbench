# Add a benchmark suite

A suite is a group of benchmark cases that share one fixture file, one Inspect task and one way to run. The harness finds suites by itself. When you add a suite, you do **not** edit the worker, the execution plan, the report exporter or the web console.

## Steps

1. **Write the fixture.** Put the cases in a JSON array under `tasks/`, one object per case. Every object needs a unique `id`. Use fictional, sanitized data only (see `AGENTS.md`).
2. **Create the suite package** `suites/<suite_id>/`. The folder name and the suite `id` must be the same.
3. **Define the suite** in `suites/<suite_id>/__init__.py`:

   ```python
   """One sentence: what the suite measures."""

   from typing import Any

   from suites import Case, Suite, require_text


   class ExampleSuite(Suite):
       id = "example"                       # same as the folder name
       label = "Example"                    # shown in the console
       description = "One sentence for the console's category list."
       fixture = "tasks/example.json"
       position = 40                        # run and display order; lower runs first

       def parse_row(self, row: dict[str, Any]) -> Case:
           for field in ("prompt", "expected"):
               require_text(row, field, self.id)
           return self.make_case(row, name=row.get("title") or row["id"], max_model_calls=1)

       def task(self, cases: tuple[Case, ...], variant: str):
           from suites.example.task import example   # import Inspect lazily
           return example([case.data for case in cases])


   SUITE = ExampleSuite()
   ```

4. **Write the Inspect task** in `suites/<suite_id>/task.py`. It takes the frozen case rows (`case.data`), not the fixture file. The case rows are the copy that was frozen when the run started, so a fixture edit during a run cannot change it. Each `Sample.id` must equal the case `id`.
5. **Put graders and helpers** in the same package, for example `suites/<suite_id>/grader.py`.
6. **Add tests** in `tests/test_<suite_id>.py`. At a minimum, check that the fixture loads, that the grader passes a correct answer, and that it fails a wrong or missing answer.
7. **Verify:**

   ```bash
   .venv/bin/python -m unittest discover -s tests
   npm run web:check
   .venv/bin/python scripts/console_bridge.py --describe   # the new suite should be listed
   ```

## Settings you can override

Set these as class attributes. Each one has a safe default in `suites/__init__.py`.

| Attribute | Default | When to change it |
|---|---|---|
| `variants` | `("base",)` | The suite has other prompt treatments. Every suite must support `base`. |
| `max_tokens` | 512 | Answers need reasoning before the final line. Check `stop_reason` in a log first. |
| `isolated_cases` | `False` | Each case needs its own process and a fresh environment, such as containers. |
| `seconds_per_call`, `startup_seconds` | 125, 60 | The suite is much slower than one generation per call. |

To give a suite its own process lifecycle, override `command()` and `timeout_seconds()`. `suites/smart_home/` shows how: its `runner.py` creates and removes disposable containers for each case.

## Rules that keep discovery working

- Do not write a suite ID as a string outside `suites/`. `tests/test_suite_registry.py` fails if you do. Read IDs from `suites.registry()` or from the `SUITE` object instead.
- Do not add per-suite branches (`if suite == ...`) to the scripts or the console. Add a `Suite` attribute or method, and give it a default that works for every suite.
- Keep the call ceiling exact. `make_case(..., max_model_calls=N)` is the most generations one case may use under one prompt variant. The plan multiplies it by the number of selected variants.
