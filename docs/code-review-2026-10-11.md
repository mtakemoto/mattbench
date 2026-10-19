# Architecture and implementation review — 2026-10-11

**Observed:** Review of the current working tree, with no implementation changes. The tree was clean at the start. Scope covered the Inspect tasks, launchers, graders, billing/export pipeline, Svelte console, container definitions, existing tests, and the older Promptfoo path. Required project guidance and planning documents were read first.

The project is small enough to evolve without a framework rewrite. Its strongest foundations are fictional fixtures, disposable HA environments, pinned dependencies, and separation of evaluator completion from model success. The immediate risks are incorrect benchmark guarantees and fragile process/artifact ownership. Splitting responsibilities and validating shared contracts would help more than adding services or class hierarchies.

There are **13 findings: 3 high, 9 medium, and 1 low**. No critical finding was established. Severity reflects this project's personal, loopback-only use: high means spending or benchmark-validity guarantees can fail; medium means recoverability, reporting integrity, or growth is materially affected; low means a bounded usability defect.

## Top three by impact relative to effort

| Rank | Finding | Why prioritize it | Estimated effort |
| --- | --- | --- | --- |
| 1 | **R01 — Disable task retries as well as API retries** | Restores the advertised paid-call stop condition. The installed library already exposes the necessary option. | Small |
| 2 | **R03 — Derive and enforce smoke call limits from the dataset** | Prevents adding a fixture from silently increasing paid requests beyond the confirmed limit. | Small |
| 3 | **R07 — Publish summary JSON atomically** | Removes a dashboard read/write race using the same temporary-file pattern already used for progress. | Very small |

R02 is also high priority because it affects grading validity, but requires more work to correlate tool results and establish execution order.

Effort estimates include focused regression checks, not a broader refactor. All recommendations and acceptance checks below are **Planned**, not implemented.

## High severity

### R01 — The smoke runner permits task retries beyond its stated request cap

**Locations:** `scripts/run-inspect-selected.py:60–72`; also `scripts/run-inspect-prompt-matrix.py:28–40`.

**Observed:** Both call `eval_set(max_retries=0)` without setting `retry_attempts`. Inspection of installed Inspect **0.3.278**, `_eval/evalset.py:484–487`, confirms that omitted `retry_attempts` becomes 10 and is forwarded to task retry handling. `max_retries` controls a different layer. The console advertises two/four smoke calls and disabled retries.

**Failure:** A failed evaluation sample can be attempted again, including after a timeout where a provider may already have billed the original request. The confirmed call count is therefore not an enforced bound. This affects individual smoke runs and the smoke phase of All cases. Correctly scored failures alone do not trigger this problem; evaluation errors do.

**Recommended fix:** Explicitly disable task retries for bounded runs, or use the existing single-pass `eval` path. Keep API retries disabled. Inspect's installed source documents `retry_attempts=0` for disabling task retries; this is preferable to wrapping the runner in another counter/retry mechanism.

**Acceptance:** Inject a provider/evaluation failure in an offline test and count actual invocation attempts. A two-sample run must never exceed two generation attempts, including errors.

### R02 — HA sequence grading checks requested calls, not successful observations

**Locations:** `inspect_pilot.py:131–175`, especially `133` and `164–174`; `tests/test_ha_trace.py:16–30`.

**Observed:** `safe_ha_trace` flattens assistant tool requests and ignores tool responses, errors, and message boundaries. An isolated probe placed search, initial read, write, and both readbacks in **one assistant message with no tool responses**; the function returned `(True, 'Tool sequence matched the pinned case.')`. The existing positive test uses this same shape.

**Failure:** The grader can accept a model that never received the required initial state or readback. A correct final state does not prove that investigation and verification happened. Array position within a multi-call request also does not prove the required observation-before-action relationship. Failed readbacks can receive the same credit as successful ones.

**Recommended fix:** Correlate requests and results by call ID. Require successful relevant read results before a dependent write is requested and successful readbacks after the write completes. Continue checking every attempted write, including failed ones, against the allowed target/action. Handle both tool-level errors and error payloads from ha-mcp.

**Acceptance:** Reject absent responses, failed reads, and a single batch pretending to perform the entire sequence. Accept a real multi-turn successful trace. Keep the existing wrong-target rejection test.

### R03 — Adding a smoke fixture silently breaks the declared model-call ceiling

**Locations:** `scripts/run-inspect-selected.py:34–37`; `inspect_pilot.py:26–35`; `scripts/run-inspect-suite.py:63–64`; `web/src/lib/server/bench.ts:149`; `web/src/routes/+page.svelte:49–50`.

**Observed:** The task consumes every row in `tasks/smoke.json`, while the runner, suite, and console separately assume exactly two rows. The runner only checks the supplied number against the hardcoded number; it never checks dataset size. An isolated probe substituted a three-sample smoke task and supplied `--max-calls 2`; the runner accepted it and handed all three samples to `eval_set`.

**Failure:** The natural growth operation of adding a third smoke case increases actual requests without increasing the confirmed cap. Progress/scoring assumptions also retain the old sample count (`scripts/run-inspect-suite.py:20`). Unlike the older paid shell launcher, the Inspect runner has no fixture-count guard.

**Recommended fix:** Build a validated execution plan from the frozen selected dataset and prompt variants, then derive the cap and expected sample IDs from that plan. Until this is shared across the console and runner, fail closed on a fixture-count mismatch. Enforce the plan again at the execution boundary.

**Acceptance:** Add/remove a fictional sample in a temporary manifest. The advertised limit and execution count must agree, or execution must stop before a model request. Verify both single-prompt and comparison runs.

## Medium severity

### R04 — A progress write failure prevents disposable-resource cleanup

**Locations:** `scripts/run-inspect-ha-pilot.py:302–311`; progress writer at `172–186`.

**Observed:** The first operation inside `finally` is `progress(...)`, which can raise on filesystem errors. An isolated probe simulated a startup failure followed by a progress-write error. Network/container creation had been attempted, but **no cleanup commands ran**.

**Failure:** Disk exhaustion, a removed progress directory, or permission changes can leak the HA/MCP containers and network precisely when failure recovery is needed. The progress error also masks the original failure.

**Recommended fix:** Make progress reporting best effort during teardown and place resource cleanup in an independently protected block. Attempt each resource cleanup even if another cleanup operation fails; retain the original failure plus cleanup diagnostics.

**Acceptance:** Inject a progress write failure after resource creation. Confirm all owned resources receive cleanup attempts and the original error is still reported. Use mocked Docker calls for this check.

### R05 — Host subprocesses can hang outside the advertised time limits

**Locations:** `scripts/run-inspect-ha-pilot.py:38–42`, `73–81`, `84–92`, `311`; `inspect_pilot.py:95–110`; `scripts/run-inspect-suite.py:76`.

**Observed:** Docker subprocesses have no process timeout. `wait_http` checks a deadline only between blocking Docker calls. The asynchronous HA scorer also invokes blocking `subprocess.run` directly. A timeout inside the container's HTTP request does not bound the Docker client/daemon operation itself.

**Failure:** A stalled Docker daemon or `docker exec` can block setup, grading, or cleanup indefinitely. Blocking the scorer's event loop also prevents normal asynchronous cancellation from taking effect promptly. The suite and console remain occupied with no effective overall deadline.

**Recommended fix:** Add bounded subprocess execution and explicit terminate/kill handling. Use asynchronous subprocess handling in the scorer so cancellation remains effective. Give setup, evaluation, and teardown separate bounded deadlines; ensure an outer worker timeout still performs cleanup.

**Acceptance:** Substitute a child process that never exits and verify bounded termination, a failed/interrupted job outcome, and cleanup attempts. Do not simulate this against production HA.

### R06 — Job lifecycle ownership allows premature unlocking and loses completion on restart

**Locations:** `web/src/lib/server/bench.ts:118–134`, `183–211`, especially `188`.

**Observed:** The web process owns billing, export, and terminal status through child event callbacks. It clears `pid` before billing/export while status remains `running`. After ten minutes from job start, `currentJob` interprets a missing PID as a stopped worker. An isolated temporary-file probe of an eleven-minute-old exporting job returned `interrupted`.

**Failure:** A long run entering billing/export can be marked interrupted while that work is active. `startJob` then permits another run; the older completion callback can overwrite the newer `job.json`. Separately, restarting the console loses the callbacks needed to finish an existing worker's billing/export and publish terminal status, even if the worker later completes.

**Recommended fix:** Let one worker own the complete lifecycle, including billing, export, and durable terminal state. Track that worker through all phases. Use job-ID-checked updates and a single-run lock; reconcile persisted jobs on startup. A small local worker and atomic files are sufficient for this project.

**Acceptance:** Simulate a run older than ten minutes entering export, and a console restart while a worker runs. Neither scenario should permit overlapping work or allow an old completion to overwrite a newer job.

### R07 — Summary publication races with dashboard reads

**Locations:** `scripts/inspect-report.py:90–91`; `web/src/lib/server/bench.ts:95–98`; `web/src/routes/+page.svelte:133–141`.

**Observed:** The exporter writes directly to `summary.json`, truncating the existing file before writing. The console synchronously reads and parses that same file on its polling path. There is no parse-error handling around `rows()`.

**Failure:** A poll during the write can parse an empty or partial document and return an error. If export is terminated during publication, the broken dashboard can persist until the next successful export. More historical rows increase the publication window.

**Recommended fix:** Write the complete summary to a unique temporary file in the same directory, then atomically replace the destination. Preserve the last valid summary on export failure.

**Acceptance:** Repeated reads during a deliberately slowed publication must always see a complete old or new JSON document. Terminating the writer before replacement must leave the previous summary readable.

### R08 — One damaged historical artifact blocks all future report exports

**Locations:** `scripts/inspect-report.py:25–35`; `web/src/lib/server/bench.ts:27–28`; related suite path `scripts/run-inspect-suite.py:85–86`.

**Observed:** Export scans all historical billing JSON, timing JSON, and `.eval` files without per-artifact error isolation. A temporary directory containing one malformed historical timing file caused the entire export to raise `JSONDecodeError`. The console timing reader also parses each file without protection. `case_score` exceptions can similarly escape the suite after a child succeeds.

**Failure:** An interrupted write or damaged old log can break every later export and cause otherwise successful evaluations to show a failed job. A score-reading exception also prevents later suite cases from running, bypassing the intended continue-after-case-failure behavior.

**Recommended fix:** Catch and record errors at the individual artifact boundary, preserve valid results, and surface an explicit incomplete-report warning. Make suite score extraction return an explicit unavailable/error result without discarding later cases. Do not silently convert unreadable records into passes or zero cost.

**Acceptance:** Include one corrupt file alongside valid completed records. Valid rows must remain available, the damaged record must be reported, and later suite cases must still execute.

### R09 — Billing can label a partial total as complete

**Locations:** `scripts/openrouter-billing.py:57–59`, `72–77`, `85`; `scripts/inspect-report.py:54–55`.

**Observed:** Model events without a response ID are removed before `expected_calls` and completeness are computed. An isolated probe supplied two model events, one lacking an ID; billing reported **1/1**, returned success, and emitted a numeric total for only one call.

**Failure:** A timeout or incomplete provider response can leave an attempt without an ID even though it may have incurred a charge. The exporter can replace usage cost with the partial billed sum and display it as the exact total. Actual charging in this situation is **Unknown**; the report must preserve that uncertainty.

**Recommended fix:** Track total generation attempts, billable IDs available, successfully queried IDs, and unknown attempts separately. Emit an exact total only when accounting is complete; otherwise retain an explicitly partial amount and unknown status. Deduplicate IDs when summing.

**Acceptance:** Test a missing response ID, unavailable billing lookup, repeated ID, and fully billed run. Only the fully accounted run should produce an unqualified complete total.

### R10 — Polling work grows with the complete history and can accumulate requests

**Locations:** `web/src/routes/+page.svelte:133–141`; `web/src/lib/server/bench.ts:23–34`, `95–108`; `web/src/routes/api/overview/+server.ts:5–8`.

**Observed:** Every 1.8 seconds, including idle periods, the browser requests all rows and timings. The server synchronously reparses the full summary and every timing file. `setInterval` starts the next fetch without waiting for the previous one, with no cancellation or error handler. The UI then rebuilds its history groupings from the returned rows.

**Failure:** As history grows, each open tab repeatedly causes work proportional to the entire archive. Slow requests overlap, can arrive out of order, and can replace newer job state with older responses. Network failures produce rejected promises without a useful connection status.

**Recommended fix:** Separate lightweight job polling from result-history retrieval. Cache/index immutable timing and summary data, reload on revision changes, and load history on demand. Use a single in-flight poll with cancellation and backoff; pause or slow it when idle/hidden. No distributed cache is needed.

**Acceptance:** With synthetic historical data and a delayed overview response, verify one poll remains in flight, old responses cannot regress state, and unchanged history is not reparsed/transferred every interval.

### R11 — The Pi scope scorer accepts keyword fragments as a correct instruction

**Locations:** `inspect_pi.py:72–85`; expected behavior in `tasks/agent-instructions.json:8–13`.

**Observed:** Correctness is based on the presence of three groups of substrings plus sentinels and the phrase `staging catalog`. Text such as `brittle research promptly` meets the general-rule predicate despite not expressing the requested behavior. Conversely, a valid equivalent using different wording can fail. The permission check establishes where a phrase appears, not whether permission is correctly scoped.

**Failure:** The result overstates semantic instruction-following success. It does not verify explaining the risk, researching before extending the workaround, or the meaning/scope of the access rule. This is material for a model-comparison benchmark even though the current task is a pilot.

**Recommended fix:** Keep objective preservation/path checks separate from semantic rule correctness. Either constrain the fixture to an explicitly verifiable output contract or report semantic completion as requiring a reviewed rubric. Do not silently equate keyword presence with the full task assertion. Freeze the revised rubric before comparisons.

**Acceptance:** Check valid paraphrases, incomplete keyword fragments, negated instructions, and globally scoped permissions. Document any remaining semantic uncertainty rather than awarding unconditional completion credit.

### R12 — Shared policies and data contracts are duplicated across orchestration and UI

**Locations:** `web/src/lib/server/bench.ts:9–12`, `37–69`, `138–211`; `web/src/routes/+page.svelte:7–13`, `134–139`; `scripts/run_inspect_settings.py:40–65`; provider setup in `scripts/run-inspect-selected.py:39–57` and `scripts/run-inspect-ha-pilot.py:204–226`.

**Observed:** Provider validation, environment handling, model-ID rules, cap logic, job types, and case types are repeated. The backend module owns catalog I/O, config parsing, history reads, job validation, process startup, billing, export, and recovery. The page owns wire types, aggregation, polling, submission, and a large amount of compressed markup. File JSON is generally accepted through casts or unvalidated dictionary access.

There is already behavioral drift: the web `.env` parser removes matching quotes, while the Python local parser retains them; the web model-ID regex accepts `:`, while `local_settings()` rejects it. Thus a setting accepted by the console can fail through a local CLI entry point.

**Impact:** This is a concrete **DRY** and **single-responsibility** problem. New sources/case types require coordinated edits in multiple layers, while unsafe casts hide contract mismatches. Dense one-line transformations and nested completion callbacks also weaken self-documenting code. No specific Liskov-substitution violation was established; introducing inheritance solely to satisfy SOLID would add little value here.

**Recommended fix:** Extract a small Python provider/config module, a validated manifest/execution-plan boundary, a durable job worker, and a result reader. Share browser/server DTOs from a module with no server-only imports. Give the page focused data/aggregation helpers and components with readable formatting. Validate JSON at the process boundary, with contract checks across Python and TypeScript. Preserve the older Promptfoo implementation as a historical path rather than forcing all generations of the harness into one abstraction.

**Acceptance:** The same supported config/model IDs should behave consistently through CLI and console. Invalid case/job/summary payloads should fail with explicit diagnostics. Adding a provider should not require duplicating lifecycle code; adding a case should not require editing call-count constants in the page.

## Low severity

### R13 — The selected runner rejects its own default run ID

**Location:** `scripts/run-inspect-selected.py:26–30`.

**Observed:** Omitting `--run-id` generates `%Y%m%dT%H%M%S%f`, then immediately requires the value to contain only digits. The literal `T` makes every generated default invalid. Running the CLI without that optional flag reproduced an argument error before endpoint discovery.

**Failure:** Standalone CLI use fails despite valid required arguments. The web path hides the problem by always supplying a digit-only ID.

**Recommended fix:** Use one run-ID constructor/validator consistently, or make the argument required if callers must own identity.

**Acceptance:** An omitted ID must produce a valid unique ID and advance to mocked endpoint validation; explicitly invalid IDs must still fail.

## Verification and limits

**Observed — 2026-10-11:**

- `.venv/bin/python -m unittest discover -s tests -v`: **7 tests passed**.
- `npm run web:check`: **0 errors, 0 warnings**.
- Offline probes reproduced R02, R03, R04, R06, R08, R09, and R13 using temporary data or mocked dependencies. R01 was verified against the installed, pinned Inspect source. Other findings are grounded in static control/data flow; their failure scenarios were not exercised against live infrastructure.
- The Svelte skill's offline autofixer command was attempted, but `@sveltejs/mcp` was not cached (`ENOTCACHED`). The existing Svelte checker ran successfully; no dependency installation was performed.
- No paid or local model generations, Docker launches, production HA calls, or production-state changes were made. No raw run logs, credentials, or private inventories were copied into this report. Only this report was added to the repository.

**Unknown:** Live Docker failure behavior, provider billing on timed-out requests, and the history size at which polling becomes noticeably slow. The findings identify code paths and correctness gaps; they do not claim those incidents have already happened in the owner's environment.

## Suggested implementation order

1. Fix request bounds (R01/R03), atomic summary publication (R07), and trace validity (R02) before further paid comparisons.
2. Make teardown and job ownership dependable (R04–R06), then isolate damaged artifacts and incomplete billing (R08/R09).
3. Extract the small shared boundaries in R12 while addressing polling and semantic scoring (R10/R11). Fix R13 alongside run-ID consolidation.

Keep the current fixture-driven approach, single-machine execution, and existing tools. A database, queue service, plugin framework, or wholesale rewrite is not required to address these findings.

## Implementation follow-up — 2026-10-12 UTC

The findings and observations above describe the original review snapshot. The following changes address every recommendation without changing the historical evidence.

**Observed — implementation inspected and offline paths exercised on 2026-10-12 UTC:**

| Recommendation | Implemented change |
| --- | --- |
| R01 | Disabled model API, sample-error, and task retries; confirmed call ceilings remain the maximum attempt allowance on provider failures. |
| R02 | Correlated successful tool results with request IDs, required relevant search results and expected state payloads, supported documented bulk/projected reads, and rejected failed, missing, unrelated, or out-of-order observations. |
| R03 | Derived budgets from validated fixture snapshots; rejected mismatched confirmations before discovery/launch and passed frozen inputs to evaluators. |
| R04 | Made teardown progress best effort and attempted independent resource cleanup despite publication/removal failures, preserving the original error. |
| R05 | Added independent deadlines and process-group termination/reaping for setup, evaluation, cleanup, Docker commands, and asynchronous scorer reads. |
| R06 | Moved the complete lifecycle into a detached Python worker with an exclusive lock, identity-checked atomic updates, and lock-based reconciliation after console restarts. |
| R07 | Published summaries through unique same-directory temporary files and atomic replacement, preserving the prior file on publication failure. |
| R08 | Isolated damaged artifacts with explicit report warnings; unreadable case scores remain unavailable and do not stop later cases. |
| R09 | Counted all generation attempts, available/queried IDs, unknown attempts, and lookup failures; deduplicated charges and separated exact totals from partial known charges. Legacy accounting is explicitly incomplete. |
| R10 | Separated job/revision polling from on-demand cached history; serialized and cancelled polls with backoff, visible errors, and a submission-generation fence against stale responses. |
| R11 | Split objective Pi preservation/placement gates from a frozen manual semantic rubric. Passing gates and legacy keyword outcomes remain unscored pending review. |
| R12 | Shared Python provider/config and execution-plan boundaries; extracted durable worker and cached result reader; shared validated TypeScript DTOs, polling/aggregation helpers, and focused status/guard components. |
| R13 | Consolidated digit-only run-ID construction and validation; omitted IDs now advance to endpoint validation. |

### Verification

- `.venv/bin/python -m unittest discover -s tests -v`: **57 tests passed**. Coverage includes retry bounds, fixture changes, unsafe HA traces, supported bulk/projected state reads, subprocess timeout/cancellation, cleanup failure handling, worker lock/restart ownership, atomic publication, damaged artifacts, billing uncertainty, semantic-review boundaries, and legacy Pi accounting.
- `npm run web:check`: **0 errors, 0 warnings**. `npm run web:build`: **successful production build**.
- Actual detached-worker smoke runs in a temporary repository copy against a deterministic loopback stub completed base smoke with **2 attempts**, both variants with **4**, and an expanded three-row fixture with **3**. A stale two-call confirmation for that expanded fixture was rejected with **0 attempts**. HTTP 500 responses produced **3 attempts within the confirmed three-call cap**, followed by a failed job. The worker exported **11 rows**.
- Python-to-TypeScript boundary smoke accepted both colon and tilde model selectors, validated the four case DTOs and 27 existing summary rows, and rejected invalid case/job/summary payloads. Partial hosted costs remained unknown totals; fully accounted zero cost remained zero.
- Actual HA scorer API smoke used fictional transcripts and real bounded local Python subprocesses for state reads, without Docker or HA access. Documented bulk observations scored **1**; omitting a required bulk entity scored **0** even though the final-state fixture remained correct. The supported bulk-read regression failed before normalization and passed afterward.
- The final timeout regression handles both procfs `ENOENT` and `ESRCH` when init reaps a terminated descendant, while still rejecting live descendant states. The final 57-test rerun passed; upstream Inspect/AnyIO deprecation and resource warnings were not suppressed.
- The actual console displayed report warnings and partial billing details. A delayed 4.5-second overview response produced **at most one in-flight poll** and **zero unchanged-history requests**. A browser-only intercepted run response confirmed that an older overview could not replace the newer submitted job; no evaluation was launched by that browser fixture.
- Desktop and 390-pixel mobile screenshots verified the rendered result surface. Mobile document width stayed at 390 pixels; the wide score table scrolled within its container.
- The offline exporter regenerated the ignored local summary with **27 rows**, retaining incomplete-billing warnings and marking archived Pi keyword outcomes unreviewed.

**Unknown:** Revised Docker teardown/failure behavior against live containers and provider charging for timed-out requests. Pi semantic completion still requires the documented review; no new automatic semantic claim is made.

No real benchmark model generations, paid benchmark evaluations, Docker launches, production HA calls, or production-state changes were made during this follow-up. Router and coding-worker calls were separate from benchmark evaluation. Raw logs, credentials, request IDs, private inventories, and browser fixtures were not added to Git.
