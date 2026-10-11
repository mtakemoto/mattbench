# Inspect AI replacement pilot

## Purpose and status

**Reported — 2026-10-10:** The owner wants to pilot Inspect AI as a possible replacement for Promptfoo and expects to build a richer dashboard from evaluation data later. A Docker image tailored to each task family is preferred over a general-purpose cached image.

**Observed — 2026-10-10 Pacific / 2026-10-11 UTC:** Inspect AI `0.3.278` ran the two existing no-tool smoke questions and a new disposable coding case against the configured local FreeToken model. The direct Python dependencies are pinned in [`requirements-inspect.txt`](../requirements-inspect.txt). No OpenRouter or production Home Assistant request was made.

| Case | Result | Tokens | Sample time | Tool calls |
|---|---:|---:|---:|---:|
| Strawberry letter count | Pass | 361 | 4.656 s | 0 |
| Car wash transport | Fail | 301 | 3.621 s | 0 |
| Fix fictional `clamp.py`, first cached-image run | Pass | 8,210 | 17.725 s | 5 |
| Fix fictional `clamp.py`, purpose-built image verification | Pass | 8,036 | 18.552 s | 6 |

The local model returned the configured Qwen 3.6 variant as the concrete response model. Inference settings: `temperature=0`, `max_tokens=512` per request, zero model API retries, 120-second request timeout, one sample and task at a time. The coding task has a six-turn and 120-second sample limit. Inspect's reported `total_cost` is null for this local model; electricity and hardware cost were not measured. The original Promptfoo local smoke also scored 1/2, but these are separate calls and their latency and token counts are not a controlled framework comparison.

## What the pilot proved

**Observed:** [`inspect_pilot.py`](../inspect_pilot.py) loads the existing smoke JSON directly. Inspect's exact-match scorer grades final answers without Promptfoo's reasoning-display adjustment. Its built-in `react` loop gave the local model a shell tool, staged [`clamp.py`](../fixtures/coding/clamp.py) inside a fresh Docker container, and ran an objective hidden behavior scorer against the resulting file. The scorer ran inside the sandbox; it did not execute model-generated commands on the host. The coding case passed twice. The second run used the new [`Dockerfile`](../inspect/Dockerfile), based on a digest-pinned official Python image with Bash, Git, and ripgrep, and executed as an unprivileged user. [`compose.yaml`](../inspect/compose.yaml) disables container networking, drops capabilities, and sets process, CPU, and memory limits. No host home or repository is mounted into the sample container. Docker Compose validated, and no pilot container remained afterward.

**Observed — build review:** The first custom-image build used the repository root as its Docker context. That could have made ignored local configuration available to the Docker daemon. The context is now limited to `inspect/`, with a [Docker ignore file](../inspect/.dockerignore) allowing only the Dockerfile into the build context. The image has no repository files or secrets. The revised Compose configuration rebuilt successfully; its runtime behavior is the same image configuration as the passing unprivileged run.

**Observed:** Inspect's `.eval` logs contain each sample's score, timing, model usage, response model ID, and tool events. [`inspect-report.py`](../scripts/inspect-report.py) exports these fields, task and Inspect versions, inference settings, and run IDs to the ignored `artifacts/inspect/summary.json`. This is the data contract for a later dashboard. It intentionally omits prompts, raw output, tool arguments, and private addresses. Use Inspect's local viewer for transcript inspection; do not publish raw logs.

## Reproduce

Use Python 3.12, Docker Engine and Compose, and the configured loopback FreeToken endpoint. Keep the existing `.env` ignored. From the repo root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-inspect.txt
.venv/bin/python scripts/run-inspect-local.py
.venv/bin/python scripts/inspect-report.py
.venv/bin/inspect view --log-dir artifacts/inspect
```

`--task smoke` or `--task coding` runs only one part. The launcher accepts only an HTTP loopback `/v1` base URL, confirms that the exact model is served, strips common paid-provider keys from its process, and never falls back to OpenRouter. Raw logs and summary JSON remain in ignored `artifacts/inspect/`.

## Replacement decision

**Observed — 2026-10-11 UTC:** The three replacement gates are now exercised. Inspect is suitable as the primary evaluation engine for this repository. Keep Promptfoo's existing runs as historical baselines; new task families and the app report use Inspect logs. This is a framework decision, not a model ranking.

| Gate | Observed result | Boundary |
|---|---|---|
| Real ha-mcp with disposable Synthetic Home | `ha-mcp` 7.1.0 talked to Home Assistant 2026.10.1 on an internal Docker network. Local Qwen changed only the fictional Coordinator target to 68°F; the head stayed at 74°F. Objective state score: pass, 49.01 s, 46,997 reported tokens. | One chained write case; 21 MCP events include errors, so efficiency and tool handling need work. No production connection. |
| Actual agent harness | Pi 1.1.0 ran inside a networkless Inspect sandbox via the agent bridge. On the instruction-scope task, it edited files but copied a project-only permission into the global file; objective score: fail. The second run used 6 model calls, 15,786 tokens, 13 Pi tool calls with one error. | Pi's JSON event stream required a small parser to summarize its internal tools; Inspect did not emit those as native `ToolEvent`s. This measures Pi, not Codex. |
| Model × prompt report | Inspect `eval_set` ran the pinned base and careful variants against local Qwen, then repeated the plumbing with Inspect's deterministic mock model. Qwen scored 1/2 on each variant. The exporter records variant, model, score, latency, usage, and log path per sample. | The mock rows prove report plumbing only. Two real questions cannot establish whether the careful prompt helps generally. |

The Python adapter around Pi's JSON event stream is the material integration cost. It is limited to event counting and tool names; the scorer still inspects final files in the disposable sandbox. The [agent bridge](https://inspect.aisi.org.uk/agent-bridge.html), [MCP tools](https://inspect.aisi.org.uk/tools-mcp.html), [eval sets](https://inspect.aisi.org.uk/eval-sets.html), and [eval logs](https://inspect.aisi.org.uk/eval-logs.html) provide the reusable execution and data layers. A custom report remains justified because the owner wants model and prompt comparisons in one app.

**Planned:** Expand the synthetic HA suite and held-out cases, grade unrelated state/file changes, repeat finalists, and record route/provider cost for hosted models. The current coding case checks only clamp behavior. Local compute cost and broader model performance remain **Unknown**. No paid API or production Home Assistant call was made during this Inspect pilot.
