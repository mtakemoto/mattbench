# Overview

With the sheer number of AI agents coming out now and claims of other models "benchmaxxing" (AKA training to the test), I decided to sic an agent on writing my own personal benchmarking suite of test cases I'm familiar with.  I try to keep all of the test cases personally relevant and verifiable, with familiar things like laptop shopping and smart home automation that have a result that I can hold in my head.

This project provides a web UI to test models against that suite.  The models can be either local, via openrouter or on another device on your network.

The main focus of this project is finding good and cheap models capable of doing specific things, not really on validating frontier models (yet, anyway).  Below, my agent will get you familiar with the tech stack and advise you on how to run it yourself.


## What it tests

Each **suite** is a small group of cases with an objective grader. No LLM judge is used.

| Suite | Cases | What the model must do | Needs |
|---|---:|---|---|
| Smoke questions | 2 | Answer short reasoning questions (letter count, car-wash trip) with one exact answer. | Nothing extra |
| Smart home | 2 | Find, change, and read back Home Assistant entities through the real [ha-mcp](https://github.com/homeassistant-ai/ha-mcp) server. Each case gets a fresh, disposable [Synthetic Home](https://github.com/allenporter/home-assistant-synthetic-home) container. The grader checks the final entity state and the tool trace. | Docker |
| Laptop shopping | 13 | Pick the laptop from a fixed ten-laptop catalog that fits a buyer persona, or answer ALL/NONE for trick questions. | Nothing extra |

A handful of cases screens models. It does not prove that one model is better than another in general.

## How it works

```
suites/<id>/          one package per suite: fixture, Inspect task, grader, limits
   │
   ▼
scripts/execution_plan.py   freezes the selected cases and the model-call ceiling
   │
   ▼
scripts/benchmark-worker.py runs each case with Inspect AI, collects billing,
   │                        and exports sanitized rows
   ▼
artifacts/inspect/          raw logs + summary.json (Git-ignored)
   │
   ▼
web/                        SvelteKit console: pick a model, run, view results
```

- **[Inspect AI](https://inspect.aisi.org.uk/)** is the evaluation engine.
- **The console** (`web/`) is the main entry point. It discovers suites from `suites/`, so it has no suite-specific code.
- **Model sources:** a local OpenAI-compatible server ([FreeToken](https://github.com/FlashML-org/FreeToken) or similar), [OpenRouter](https://openrouter.ai/), or any other OpenAI-compatible `/v1` endpoint on loopback or your private network. A local run never falls back to a paid provider.

## Get started

### Prerequisites

- Linux (the only platform tested)
- Python 3.12
- Node.js 22 and npm
- Docker, for the Smart home suite only
- At least one model source: a local OpenAI-compatible server, an OpenRouter API key, or another `/v1` endpoint

### 1. Install

From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-inspect.txt
npm --prefix web ci
```

### 2. Configure model sources

```bash
cp .env.example .env
```

Fill in only what you use. `.env` is Git-ignored.

- `MATTBENCH_LOCAL_BASE_URL`: your local server's base URL, ending in `/v1`
- `MATTBENCH_LOCAL_MODEL`: an exact model ID from that server's `/v1/models`
- `OPENROUTER_API_KEY`: your OpenRouter key

For a different endpoint, you can also type its `/v1` address into the console instead.

### 3. Build the Smart home image (optional)

Skip this step if you do not run the Smart home suite.

```bash
docker build -t mattbench-synthetic-ha:2026.10.1-v1 inspect/ha
```

This image is Home Assistant with the pinned Synthetic Home integration. The pinned ha-mcp image is pulled by digest when it is first used. Benchmark containers run on an internal Docker network and never use production Home Assistant credentials.

### 4. Run the console

```bash
npm run web
```

Open <http://127.0.0.1:5173>. Choose a model source and a model, pick **Run everything** or a category, and start the run. The console shows progress per case, and you can cancel. Open **Results** for the scorecard and per-case grader explanations.

The console listens only on loopback and has no authentication. Do not expose it to a network.

### Paid runs

Before an OpenRouter run, set a dollar limit on your OpenRouter workspace or key. The console asks you to confirm that limit and shows the maximum model calls before it starts. It cannot stop a request that is already in progress, so the limit at OpenRouter is the real guard. Retries are disabled. After the run, the worker reads the actual charges from OpenRouter. Free (`:free`) models skip the confirmation.

### Check the code

```bash
.venv/bin/python -m unittest discover -s tests   # Python harness tests, no model calls
npm run web:check                                # Svelte type and lint checks
```

## Repository map

| Path | Contents |
|---|---|
| `suites/` | Suite registry. One package per suite. |
| `tasks/` | Case fixtures (JSON), all fictional and sanitized |
| `fixtures/` | Supporting data: synthetic home inventories, laptop catalog, coding repos |
| `scripts/` | Execution plan, worker, suite runner, report export, OpenRouter billing |
| `inspect/` | Dockerfiles for the Synthetic Home image and sandboxes |
| `web/` | SvelteKit console. See [web/README.md](web/README.md) for its internals. |
| `tests/` | Python unit tests |
| `docs/` | Plans, run reports, and design notes |
| `artifacts/` | Run output (Git-ignored) |

## For AI agents

Read [AGENTS.md](AGENTS.md) first. It contains the safety rules and the evidence conventions (**Observed**, **Reported**, **Planned**, **Unknown**). In summary:

- Write tests run only against a disposable synthetic Home Assistant. Never change the live home.
- Never commit keys, tokens, private addresses, raw traces, or live entity IDs.
- Get an explicit dollar cap before you make any paid model call.

Then read, in this order:

1. [Add a benchmark suite](docs/adding-a-suite.md): how the suite registry works
2. [Evaluation plan](docs/evaluation-plan.md): goals, scoring, and run rules
3. [Context handoff](docs/context-handoff.md): why the project exists and the original research

## Further reading

- **Run reports:** [GLM 5.3 Flash suite run](docs/glm-flash-suite.md), [Inspect AI pilot](docs/inspect-pilot.md), [first hosted smoke](docs/first-hosted-smoke.md), [first local smoke](docs/first-local-smoke.md), [first HA local](docs/first-ha-local.md)
- **Suite designs:** [smart home containers](docs/ha-container-benchmark.md), [laptop shopping](docs/laptop-shopping-benchmark.md)
- **Planned, not yet runnable:** [agent instruction cases](docs/agent-instruction-benchmarks.md) (Pi agent), [even/odd coding](docs/coding-even-odd-benchmark.md), [clean-code style](docs/clean-code-benchmark-plan.md)
- **Background research:** [framework review](docs/benchmark-framework-review.md), [upstream ha-mcp test review](docs/upstream-ha-mcp-review.md)

### Legacy Promptfoo baselines

The project started on [Promptfoo](https://www.promptfoo.dev/) before it moved to Inspect AI. The original configurations stay as historical baselines. Install them with `npm ci --ignore-scripts` at the repository root. Then use `npm run smoke` (offline, deterministic), `npm run smoke:local`, `npm run smoke:openrouter`, `npm run ha:local`, or `npm run ha:offline`. The run reports above describe the settings and results. New work uses Inspect AI and the console.
