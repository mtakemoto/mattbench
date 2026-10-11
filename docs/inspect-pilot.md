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

**Planned:** Inspect is a promising primary evaluation engine: it handled the smoke matrix inputs, a multi-turn file edit, disposable Docker state, objective grading, and exportable records without a custom agent loop. Keep the existing Promptfoo configurations as historical baselines while evaluating the next gates. Do not run every candidate twice through both frameworks.

Before replacing Promptfoo for future runs, prove (1) real ha-mcp plus disposable Synthetic Home services in an internal Compose network, (2) one agent-instruction case with the *actual* candidate harness when harness behavior is under test, and (3) a multi-model, multi-prompt report built from Inspect logs. Inspect's built-in `react` tests a model under Inspect's agent loop; it does not measure Pi's or Codex's own instruction-loading behavior. The current coding case is a tool and sandbox pilot, not a representative coding benchmark: its hidden assertions do not yet grade unrelated file changes. A handful of results cannot rank models broadly.
