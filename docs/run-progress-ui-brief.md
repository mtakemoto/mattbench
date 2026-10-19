# Live run progress: design brief

**Status:** Planned, not built. Shaped on 2026-10-19. The owner chose **strip + expandable grid** and **live outcomes**.

## Job and audience

The owner starts a run and watches it from any view (Run, Results, Activity). They need to know how far the run is in **cases**, which category and case is running now, and whether something is going wrong early. For example, every answer may be cut off by the token limit. The surface is in Operate mode: you should be able to read it at a glance, and it should stay calm while it updates.

## The problem today

`LiveRun` and `JobStatus` show "3 of 4 cases finished". The 4 is the number of plan **entries** (child processes). That is an internal detail. Smoke counts as 1 entry, each smart home case is 1 entry, and all 13 laptop cases together are 1 entry. Nothing shows progress inside an entry.

## Wording

| Word | Meaning | Shown in the UI? |
|---|---|---|
| **case** | One fixture row, which is one Inspect sample. This is the unit the owner counts. | Yes. Every count is in cases. |
| **category** | One suite. "Category" is already the word the run setup uses. | Yes |
| entry | One child process | **Never.** It stays internal. |

Copy patterns:
- Collapsed: `9 of 17 cases · Laptop shopping 5 of 13 · AI Engineer (128B LLM)`
- Phase captions come from the existing progress messages: "Starting disposable Home Assistant", "Generating", "Scoring".

Source fix: rename the job fields so the code says the same thing. `totalCases`/`completedCount` become `totalEntries`/`completedEntries`, and new `cases[]` records hold the case counts.

## Hierarchy and layout

**Collapsed strip** (the default; sticky across all views, as it is today):
- spinner
- case progress `9 of 17 cases`
- current category and its count
- current case name, with the phase caption under it
- live tally `5 pass · 3 fail`
- calls used / maximum
- progress bar (in cases)
- expand toggle

**Expanded** (remember the choice in `localStorage`): one row per category:

```
Smoke questions      ●○              2/2   1 pass · 1 fail
Smart home           ✕●              2/2   0 pass · 1 fail · 1 error
Laptop shopping      ●●●●◐○○○○○○○○   5/13  4 pass
                     ↳ AI Engineer (128B LLM) · Generating
```

- Each mark is a focusable element. Its tooltip, and its accessible name, give the case name, the outcome, the number of calls and the grader explanation.
- Marks wrap. They stay readable up to about 100 cases per category.
- When the run ends, the strip leaves (as it does today). The same grid component, in its final state, moves into the Run view's `JobStatus` card. That keeps one component and one mental model.

**Early warning:** when 3 or more cases in a category are cut off at the token limit, the strip shows a coral note: *"3 answers cut off at the token limit — scores may measure the limit, not the model."* This is the failure that hid in the first laptop run.

## States

Never show a state by colour alone. Each state has a shape, a label and an accessible name.

| State | Mark | Notes |
|---|---|---|
| queued | ○ hollow | Known from the frozen plan at start, so the grid is complete from the first second |
| running | ◐ half, slow pulse | Only one at a time; it shows the phase caption |
| pass | ● lime (`pass-signal`) | |
| fail | ● coral (`coral-miss`) | |
| truncated | ● coral + notch | Counts as fail, and also adds to the early warning |
| unscored | ◌ dashed | Waiting for review (the Pi semantic rubric) or score unavailable |
| error | ✕ | The evaluator failed, not the model. Applied to every case of the failed entry |

## Data the backend must publish

These rules keep the plan suite-agnostic:

1. **At job start**, the worker writes `cases: [{id, suite, name, state: "queued"}]` from the frozen plan into `job.json`. The console already knows suite labels from the catalog, so it needs no suite IDs.
2. **During a run**, register an Inspect `Hooks` subclass (`on_sample_start` and `on_sample_end`, checked in Inspect 0.3.278) in the two places that call Inspect: `scripts/run-inspect-cases.py` and `suites/smart_home/runner.py`. Put the subclass in one shared module, for example `scripts/case_progress.py`.
   - On sample start, it writes `{id, state: "running"}`.
   - On sample end, it writes `{id, state, passed, truncated, calls}`. Use `scripts.inspect_results.sample_outcome` for `passed`.
   - It writes to a per-entry file, `<run>.cases.<entry>.json`, so the child never races the orchestrator's `progress.json`.
   - Sample ID equals case ID; this is already true for every suite.
3. **`currentJob()` in `web/src/lib/server/bench.ts`** merges the per-entry files over the queued list. The merge already exists for `progress.json`.
4. **If a child fails**, the orchestrator marks the entry's unfinished cases `error`.

Cost: one small JSON write per sample. No extra polling. The console already polls `/api/overview` every 1.8 s while a run is going.

## Accessibility and responsive behaviour

- The progress bar's `aria-valuenow`/`valuemax` count cases.
- `aria-live` announces only when a category finishes, not each mark.
- Respect `prefers-reduced-motion`: no pulse, and a static half mark for the running case.
- At phone width (≤620px), the collapsed strip drops the case name and keeps `9/17 · Laptop 5/13`. The expanded rows stack.

## Scope and anti-goals

- **In scope:** `LiveRun`, `JobStatus`, a shared `CaseGrid` component, a pure TS function `runProgress(job, suites)` in `lib/`, the hook module, and the job contract fields.
- **Not in scope:** a stop/cancel button, history charts, and changes to the Results/Activity layout.
- **Anti-goals:**
  - No suite IDs in `web/src`; the guard test enforces this.
  - No new polling endpoint.
  - No percentage-only progress.
  - Do not hide failures until the end.

## Open decisions for the owner

1. Should the visible word be **category** or **suite**? This brief uses *category* to match the run setup.
2. Should the expanded state be remembered per browser (as proposed) or always start collapsed?
3. The early-warning threshold of 3 truncated cases is a guess. Should it be per category or for the whole run?
