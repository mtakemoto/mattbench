# Personal agent benchmarks

Personal evaluation workspace for comparing models and agent setups on tasks that matter here: Home Assistant investigation through `homeassistant-ai/ha-mcp`, safe smart-home changes in an isolated test home, and coding in a disposable repository. The aim is a useful decision from a small number of bounded runs, not a public leaderboard.

The first two no-tool cases are in [tasks/smoke.json](tasks/smoke.json). [Promptfoo](https://www.promptfoo.dev/docs/configuration/guide/) is pinned at `0.124.1` for a local smoke run; [smoke.py](smoke.py) remains an independent offline grader. Start with [the handoff](docs/context-handoff.md), [the evaluation plan](docs/evaluation-plan.md), [the benchmark framework review](docs/benchmark-framework-review.md), and [the ha-mcp test review](docs/upstream-ha-mcp-review.md).

Two [agent instruction cases](docs/agent-instruction-benchmarks.md) cover ambiguous rule scope and discovering the active agent harness's documented user-wide instruction file. The first ran under Pi in a disposable Inspect sandbox and failed its scoped assertion. The second remains unrun.

## Inspect AI replacement pilot

[Inspect AI](https://inspect.aisi.org.uk/) `0.3.278` is now the primary engine for new benchmarks. It ran the smoke questions, a disposable coding repair, real ha-mcp against a synthetic Home Assistant container, and an actual Pi agent instruction task. The [pilot report](docs/inspect-pilot.md) records the results and limits. The Pi task failed its scoped instruction assertion; the harness and grading path worked. Install the pinned Python dependencies from [requirements-inspect.txt](requirements-inspect.txt) in an ignored `.venv`, then run `.venv/bin/python scripts/run-inspect-local.py`. Run `.venv/bin/python scripts/inspect-report.py` to export dashboard-ready, non-secret fields to ignored `artifacts/inspect/summary.json`; use `.venv/bin/inspect view --log-dir artifacts/inspect` for detailed local logs. Local launchers have no paid-provider fallback.

The new [Svelte benchmark console](web/README.md) selects a FreeToken, OpenRouter, or private OpenAI-compatible model, launches the pinned Inspect smoke set, and visualizes task-level model × prompt results. From `web/`, run `npm ci` and `npm run dev -- --host 127.0.0.1`; open `http://127.0.0.1:5173`. The app runs on loopback and requires a separate workspace cap confirmation before a paid OpenRouter launch. No paid call was made to build or verify the console.

## Run the Promptfoo smoke test

With Node 22 and npm installed, run `npm ci --ignore-scripts` and then `npm run smoke`. The command reads the two pinned tasks, uses a deterministic synthetic provider, and writes [an HTML report](artifacts/promptfoo-smoke.html) and JSON results under the Git-ignored `artifacts/` directory. It disables caching, sharing, telemetry, and remote generation. It makes no model or Home Assistant request and costs nothing. The HTML report is a local task-by-provider table; the real-provider runs are described below.

**Observed — initial setup, 2026-10-10:** `npm run smoke` passed both cases with Promptfoo `0.124.1`; the exported result shows two synthetic provider requests and zero model tokens. At that stage, no OpenRouter key or local model endpoint was available to this process. Later hosted and local runs are recorded below.

The owner chose the newest GLM Flash model for the first hosted run. [OpenRouter's GLM Flash Latest page](https://openrouter.ai/~z-ai/glm-flash-latest) currently points to [GLM 5.3 Flash](https://openrouter.ai/z-ai/glm-5.3-flash), so [the hosted configuration](promptfooconfig.openrouter.cjs) pins `z-ai/glm-5.3-flash` instead of the moving alias. Put the key after `OPENROUTER_API_KEY=` in the Git-ignored `.env` file, or export it in the process environment. After verifying the $20/week workspace cap, run `MATTBENCH_CONFIRMED_WEEKLY_CAP_USD=20 npm run smoke:openrouter`. That command accepts exactly two fixture rows, one repeat, and one provider. It writes a separate ignored report under `artifacts/`. Never paste the key into chat or commit it to Git.

The [first hosted smoke report](docs/first-hosted-smoke.md) records the original two-request run and a separate corrected verification run. The first strict score was affected by Promptfoo's reasoning display; with `showThinking: false`, GLM 5.3 Flash passed both simple cases. Both runs' usage, latency, and reported costs are preserved.

## Run against local FreeToken

Set `MATTBENCH_LOCAL_BASE_URL` and `MATTBENCH_LOCAL_MODEL` in the ignored `.env` file. Use the base URL through `/v1` and the exact model ID returned by your server's `/v1/models`; the current local values are already filled in. Run `npm run smoke:local`. The command checks that the URL is loopback and the model is served, then runs the same two tasks and grader as the hosted configuration. It clears hosted API key variables, disables OpenAI's default key fallback, and contains no OpenRouter provider. Results go to [the local HTML report](artifacts/promptfoo-local-smoke.html) and an ignored JSON export. If the endpoint or model is unavailable, the run stops without switching providers.

**Observed — 2026-10-10:** The served Qwen 3.6 variant passed strawberry (`3`) and failed car wash (`WALK`), for **1/2** on this tiny no-tool set. The run took about 50 seconds and reported 655 tokens. See [the local run report](docs/first-local-smoke.md) for settings and limits. Local compute cost was not measured.

| Smoke run | Exact answers | Run time | Tokens | Provider charge |
|---|---:|---:|---:|---:|
| [OpenRouter GLM 5.3 Flash](docs/first-hosted-smoke.md) | 2/2 | 3.3 s | 224 | $0.00008309 reported |
| [Local Qwen 3.6 variant](docs/first-local-smoke.md) | 1/2 | 50.0 s | 655 | No hosted charge; compute cost unknown |

These two prompts only check the no-tool path. The local run's first request was much slower; whether that was server warm-up is **Unknown**.

## Run the first Home Assistant MCP benchmark

Run `npm run ha:local` with the same loopback FreeToken settings in the ignored `.env`. This runs one [pinned read-only task](tasks/ha-readonly.json) against a [fictional Synthetic Home inventory](fixtures/ha/north-room.yaml). A local stdio MCP server exposes only `ha_search` and `ha_get_state`; it has no Home Assistant connection, network client, or write tools. The agent makes at most four local model requests and four tool calls. There is no paid-provider fallback. The grader requires the exact answer and a state read of the correct coordinator entity. The HTML report, JSON result, and tool-call trace are ignored under `artifacts/`.

Run `npm run ha:offline` to verify the complete Promptfoo → model API → MCP → grader path using a deterministic loopback stub. This is a harness test, not a model score. It writes separate offline artifacts.

**Observed — 2026-10-10:** The local Qwen 3.6 variant passed the first read-only case in three model requests and two MCP tool calls, using 2,226 reported tokens in 6.9 seconds. The [HA run report](docs/first-ha-local.md) records the settings, evidence, and limitations. The fixture was accepted by `synthetic-home==5.0.3`. No production Home Assistant connection was made.

For the substantive Home Assistant suite, use [real ha-mcp connected to a disposable Synthetic Home instance](docs/ha-container-benchmark.md), including chained write tasks. The handwritten MCP fixture remains only a cheap check of the agent loop. Each case starts from fresh Home Assistant state; no benchmark path uses production credentials or changes the live home.

To grade answers offline, place a JSON object such as `{"strawberry_r_count":"3","car_wash_transport":"DRIVE"}` outside the repository, then run `python3 smoke.py /path/to/responses.json`. The command prints pass/fail per case and makes no network calls.

## Intended model sources

- **OpenRouter:** fixed model IDs for fair comparisons. Discover candidates and current price, context, and tool support from its [Models API](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties). Treat `openrouter/pareto-code` as a separate, moving coding-router baseline and record the concrete response model.
- **FreeToken:** local models through its OpenAI-compatible HTTP API. Use the same tasks and scoring as hosted models, but measure local latency and hardware use separately. Local requests do not pass through OpenRouter.

The owner confirmed that OpenRouter's Pareto coding router is the intended dynamic frontier target.

## Boundaries

This repository contains plans and sanitized fixtures only. Keep API keys, Home Assistant MCP URLs, long-lived tokens, private topology, raw traces, and live backups outside Git. Production Home Assistant is read-only for benchmark work. Tests that modify entities, automations, or dashboards use an isolated synthetic Home Assistant instance.

## First implementation decisions

1. Keep the pinned Promptfoo smoke configurations as historical baselines. Use Inspect AI for new runs, objective scoring, and the app report.
2. For paid calls, use an OpenRouter workspace or dedicated key with an explicit USD limit and a fixed run/stop condition. Record usage per run; dynamic spending shutdown is optional.
3. Keep the completed mock MCP case as a harness smoke test. Build the representative HA set through real ha-mcp and disposable Synthetic Home containers.
4. Freeze model IDs, versions, prompts, tools, fixtures, and seeds for each comparison; run a small repeated finalist round.

Sources and task ideas are in the docs. No model quality or local model fit is claimed yet.
