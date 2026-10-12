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
- **OpenRouter:** Reads `OPENROUTER_API_KEY` from the same ignored `.env`. Its public model catalog powers search. Before running, enter the active workspace cap (up to the current $20 pilot ceiling) and explicitly confirm it. The cap must be configured at OpenRouter; this app does not dynamically stop a running API request based on spend. Base or careful smoke makes two calls; compare both makes four. Model API retries are disabled. After a run, a read-only billing pass fetches exact per-generation costs and routed providers; it stores totals without request IDs in ignored artifacts.
- **Other endpoint:** Enter a literal private or loopback HTTP address ending in `/v1` (for example, another local port or a private network model server). The app discovers served model IDs. This profile uses OpenAI-compatible chat completions and a local placeholder API key; endpoints requiring their own authentication are future work.

The default **All cases** run evaluates the two pinned no-tool smoke tasks together, then every HA case in the manifest, in order. It uses the base prompt for smoke and creates a fresh disposable Synthetic Home and real ha-mcp container pair for each HA case. With the current two HA cases, it allows at most 26 model generations: two for smoke and twelve per HA case. Each HA case's ceiling is pinned in `tasks/inspect-ha-cases.json`, and each has a 3-minute time limit. The suite accepts FreeToken, OpenRouter, or a private compatible endpoint. The OpenRouter workspace cap confirmation applies to any paid selection. The report shows actual model calls used, tokens, cost when available, and container setup and cleanup time.

During a suite run, a sticky status strip stays visible across the Run, Results, and Activity views. It shows the current case and phase, completed/total case count, a progress bar, and finished case outcomes with model calls. A failed evaluator process does not stop later cases; after all cases finish, the overall job is failed if any case process failed, and the case results remain available. Process success is separate from the model's score. A startup or suite-level failure also marks the job failed. Inspect export must finish successfully before a job can be reported complete. The case menu comes from the task manifests. The scorecard shows one compact row per model and prompt treatment, with aggregate score, calls, time, tokens, and cost; select Run details for the individual cases and grader explanations. Activity selects one run at a time and lists its cases. A handful of cases screens the workflow, not a model ranking. Local compute cost is not measured.

The app is for one owner on loopback. Do not expose it to a public network without adding authentication and a stronger endpoint access policy.

The app's `DESIGN.md` and `.impeccable/design.json` are relative symlinks to the repository's design system. This keeps one source of truth while allowing the design checker to discover it inside the Svelte package boundary.
