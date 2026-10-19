# mattbench console

This SvelteKit app runs locally against the repository's Inspect AI benchmark harness. It reads sanitized rows from the ignored `artifacts/inspect/summary.json` file. Raw Inspect logs and the worker log stay ignored on this machine.

From the repository root, install the pinned Python environment first:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-inspect.txt
.venv/bin/python scripts/inspect-report.py
```

Then install and run the web app from the repository root:

```bash
npm --prefix web ci
npm run web
```

Open `http://127.0.0.1:5173`. For a standalone server, run `npm run build`, then `HOST=127.0.0.1 PORT=4173 node build` from `web/`.

## Sources and run limits

- **FreeToken:** Reads `MATTBENCH_LOCAL_BASE_URL` from the repository's ignored `.env`, lists `/v1/models`, and uses the exact selected model. If the endpoint is unavailable, the run stops.
- **OpenRouter:** Reads `OPENROUTER_API_KEY` from the ignored `.env`. Its public model catalog powers search. Enter the active workspace cap (up to the current $20 pilot ceiling) and explicitly confirm it before running. OpenRouter's zero-cost `:free` model endpoints skip this paid run guard entirely: selecting one hides the guard and no cap confirmation is required or recorded. The cap must be configured at OpenRouter; the app cannot stop an in-flight API request based on spend. Model API, sample-error, and task retries are disabled. A read-only billing pass collects generation charges and routed providers afterward, without storing request IDs. An exact total is published only when every generation attempt is accounted for; otherwise the total remains unknown and known charges are labeled as a partial subtotal.
- **Other endpoint:** Enter a literal private or loopback HTTP address ending in `/v1` (for example, another local port or a private network model server). The app discovers served model IDs. This profile uses OpenAI-compatible chat completions and a local placeholder API key; endpoints requiring their own authentication are future work.

The default **All cases** run evaluates the pinned no-tool smoke tasks together, then every HA case in manifest order. It uses the base smoke prompt and creates a fresh disposable Synthetic Home and real ha-mcp container pair for each HA case. Call ceilings come from a validated, frozen execution plan: smoke fixture count times selected prompt variants, plus each selected HA case's `max_model_calls`. The current fixtures yield two calls for base/careful smoke, four for both variants, and 26 for All cases. A mismatched or missing call confirmation is rejected before endpoint discovery or worker launch. All cases and individual HA cases use the base variant. FreeToken, OpenRouter, and private compatible endpoints share the same validation and lifecycle. The report shows actual calls, tokens, cost certainty, and container setup and cleanup time.

During a suite run, a sticky status strip stays visible across the Run, Results, and Activity views. It shows the current case and phase, completed/total case count, a progress bar, and finished case outcomes with model calls. A failed evaluator process does not stop later cases; after all cases finish, the overall job is failed if any case process failed, and the case results remain available. Process success is separate from the model's score. A startup or suite-level failure also marks the job failed. Inspect export must finish successfully before a job can be reported complete. The case menu comes from the task manifests. The scorecard shows one compact row per model and prompt treatment, with aggregate score, calls, time, tokens, and cost; select Run details for the individual cases and grader explanations. Activity selects one run at a time and lists its cases. A handful of cases screens the workflow, not a model ranking. Local compute cost is not measured.

The app is for one owner on loopback. Do not expose it to a public network without adding authentication and a stronger endpoint access policy.

The app's `DESIGN.md` and `.impeccable/design.json` are relative symlinks to the repository's design system. This keeps one source of truth while allowing the design checker to discover it inside the Svelte package boundary.

## Durable worker and bounded cleanup

`scripts/benchmark-worker.py` owns evaluation, billing, export, and terminal status independently of the console process. It retains an exclusive `flock` for the entire lifecycle and checks job identity before updates. Restarting the console does not release an active run. When no worker owns the lock, a persisted running job is reconciled as interrupted rather than inferred dead from its age or a reused PID.

HA setup is bounded to 240 seconds, evaluation to 180 seconds, and cleanup to 40 seconds; individual Docker/state-read commands also have deadlines. Timed-out or cancelled child process groups are terminated and reaped. Container, network, and configuration removals are attempted independently, preserving the original failure if cleanup also fails. Billing and export have separate 120- and 180-second worker deadlines. Credentials are passed through the worker environment, not persisted in the plan, request, or job JSON.

## Reports and polling

Summary, timing, and billing files are published through unique same-directory temporary files and atomic replacement. Damaged artifacts are isolated: valid rows stay available with an incomplete-report warning. If a case's scores cannot be read, its result is unavailable rather than a pass, and the suite continues.

The initial page and `/api/overview` contain lightweight job/revision data. Results and Activity fetch `/api/history` on demand and only when its revision changes. The server caches parsed summary and timing data; unchanged polls do not reparse or transfer the complete archive. Browser polling is serialized, abortable, and slower when idle or hidden, with backoff and a visible connection error. A submission generation fence prevents an older overview response from replacing a newer submitted job.

An em dash in the cost column means the total is unknown, not zero. Run details identify partial known charges and unavailable billing. Pi scope results that pass objective preservation/placement checks remain unscored until the [frozen semantic rubric](../docs/agent-instruction-benchmarks.md#frozen-review-rubric-for-the-pi-scope-case-task-version-2) is reviewed; archived version-1 keyword scores are retained but do not count as semantic outcomes.
