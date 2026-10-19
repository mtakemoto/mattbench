# Suggested additions to AGENTS.md (for review)

**Status:** These are proposals. Nothing here is in `AGENTS.md` yet. We will review them together before any change.

**Why:** After the suite-registry refactor (2026-10-19), most remaining risk comes from agents that copy a nearby pattern without knowing the repository's rules. Cheaper models are more consistent when the rules are short, can be checked by a tool, and point to one example. Each suggestion below includes the reason for it and, where one exists, the test that enforces it.

---

## 1. Where code goes

> **Benchmark suites are discovered, never wired in.** To add or change a suite, edit only `suites/<suite_id>/` and its fixture under `tasks/`. Follow `docs/adding-a-suite.md`. Do not edit the worker, the plan, the report or the console for one suite. `tests/test_suite_registry.py` fails if a suite ID appears outside `suites/`.

*Reason:* Before the refactor, adding the laptop suite needed edits in 8 places. Two of them were missed: a run-ID allowlist in the report exporter and in billing. That is what hid the laptop rows in the run details. The guard test now catches this mistake.

> **Generic layers get generic extension points.** When one suite needs different behaviour, add an attribute or method to `Suite` with a default that works for every suite. Then override it in that suite. Do not add `if suite == ...` branches.

## 2. Reuse before writing

> Before you write a helper, search for an existing one. Use:
> - `scripts/json_files.write_json_atomic` for every JSON artifact
> - `scripts/run_inspect_settings.SOURCES`, `GENERATION` and `resolve_base_url` for providers and Inspect settings
> - `scripts/inspect_results` for pass/fail rules and run IDs
> - `web/src/lib/format.ts` for display formatting
>
> If you copy logic a second time, extract it instead.

*Reason:* The refactor removed 7 copies of the atomic-write code, 10 copies of the source list, 3 copies of the Inspect settings and 2 copies of the pass/fail rule. Small differences between copies are where bugs hide.

## 3. No hidden numbers or names

> Compute budgets, counts and limits from the data, or give them a name and a docstring. A literal such as `maxCalls == 39` or "10 laptops" is a bug that has not happened yet.

*Reason:* Before the refactor, "Run everything" included laptops only when the console sent exactly 39 calls. Adding one laptop case would have broken "Run everything".

## 4. Prove it works, in this order

> Before you report a change as done, run:
> 1. `.venv/bin/python -m unittest discover -s tests`
> 2. `uvx pyflakes suites scripts tests inspect_pilot.py`
> 3. `npm run web:check` when `web/` changed
> 4. For UI changes, open the console (`npm run web`) and check the affected view.
>
> Report the exact results. "Should work" is not a result.

*Reason:* Cheaper models often stop after the edit. A fixed checklist with exact commands removes the guesswork.

## 5. Check the harness before you blame the model

> If many cases fail the same way, open one Inspect log before you report a model result. Check `stop_reason`, an empty completion and the extracted answer. The summary now marks `truncated: true` when generation hit `max_tokens`.

*Reason:* In the 2026-10-19 run, all 13 laptop "failures" were 511-token reasoning traces with no answer. The harness caused them, not the model.

## 6. Self-documenting code

> - Name things for what they mean (`deadline_seconds`, `expected_samples`), not how they are stored.
> - Give each module a docstring that explains why it exists. Write comments only for a non-obvious reason or constraint.
> - Keep functions to one job. If a Svelte component passes about 150 lines or mixes data loading with layout, split it. The console page went from 410 lines to about 250, plus focused components.
> - Match the code around you: its naming, its comment density and its idiom.

## 7. Commits

> Commit when one logical change is complete and the checks above pass. Do not commit with failing tests. Keep each refactor separate from behaviour changes in its own commit, and name every behaviour change in the commit message (for example, "laptop max_tokens 512 → 4096").

---

## Open questions for review

1. **Laptop grader matching is loose.** `_normalize_id` maps substrings in both directions (`normalized in kid`). A very short extracted answer could match a catalog ID by accident, and phrases such as "p5" or "a16" map to particular laptops. This could produce false passes. I did not change it, because changing it changes scores. Should the grader accept only the exact `ANSWER:` line?
2. **The default `.env` local model is stale.** `MATTBENCH_LOCAL_MODEL` names `…heretic-NVFP4-MTP-FTW`, but FreeToken serves `Qwen3.6-35B-A3B-NVFP4`. The console falls back silently. Should a mismatch be shown as a warning instead?
3. **`max_tokens` for smoke and smart home is still 512.** Reasoning models may also be truncated there. Should we review a log for each suite and set a value per suite?
4. **Older Promptfoo files** (`promptfooconfig*.cjs`, `providers/`, `smoke.py`, `scripts/*.cjs|sh`) are historical baselines. Should they move to a `legacy/` folder, so agents do not copy their patterns?
