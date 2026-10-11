# Context handoff — 2026-10-10

This is a sanitized handoff for another agent. It records why this project exists and what to verify next. It is not a live Home Assistant inventory.

## Owner's objective

**Reported — 2026-10-10:** The owner wants to compare a small number of locally runnable and hosted models on real agent work: Home Assistant via `homeassistant-ai/ha-mcp`, multi-step reasoning, and coding. Paid hosted calls will use OpenRouter, and the owner wants the minimum useful number of evaluations. The owner confirmed that OpenRouter's Pareto coding router is the intended dynamic target and named [FlashML FreeToken](https://github.com/FlashML-org/FreeToken) as the local runtime.

**Planned:** A single harness will compare fixed OpenRouter model IDs and locally served FreeToken models under the same task definitions and graders. OpenRouter's Pareto router can be a separate dynamic baseline; it is not a stable individual model.

## Relevant home environment

**Observed — repository inspection, 2026-10-10:** The neighboring `homesvr-ansible` repository's `docs/current-state.md` records a successful read-only Home Assistant MCP connection on 2026-10-08, Home Assistant Core 2026.9.4, and ha-mcp 8.6.0. It records that Home Assistant owns its UI-managed integrations, dashboards, automations, and entities. The connection method and endpoint are intentionally absent from this repository. Recheck versions and capabilities before implementation. Source: `../homesvr-ansible/docs/current-state.md` and `../homesvr-ansible/docs/runbooks/connect-home-assistant-mcp.md` if this project remains beside that repository.

**Reported and documented in the neighboring repository:** The owner has used ha-mcp for investigations and bounded changes to an MXZ Coordinator controlling three Mitsubishi indoor heads, room temperature sensors, a comfort schedule, window-open drift controls, and separate Home and detailed HVAC dashboards. A bedroom Air Lab sensor was unavailable; a temporary temperature helper based on the raw head reading was used. The owner later confused a displayed MXZ room target with the raw head's internal setpoint, prompting a dashboard change. The apparent problem of continued heating at a displayed temperature above 70°F required inspecting the actual target and control state. These are excellent examples of entity-discovery, state-versus-configuration, and explanation tasks. Do not copy the owner's real entity IDs or history into public fixtures.

**Reported and documented in the neighboring repository:** Two bedroom Govee floor lamps in a light group looked different despite matching color-temperature values in Home Assistant. Direct matching RGB commands and an Adaptive Lighting RGB preference resolved the visible mismatch, confirmed by the owner. This makes a useful diagnostic task: distinguish reported state from physical appearance, identify competing integration/group behavior, and verify with a human observation. A synthetic fixture cannot prove physical color; grade whether the agent asks for or incorporates that evidence.

**Observed — local workstation, 2026-10-10:** `lscpu` reports AMD Ryzen 7 9800X3D, 8 cores/16 threads, and `free -h` reports about 60 GiB RAM. `lspci` identifies an NVIDIA GeForce RTX 5070 Ti and AMD integrated graphics. `nvidia-smi` failed to communicate with the driver in this session. GPU memory, driver readiness, CUDA version, model fit, and FreeToken performance are **Unknown**. Check these before selecting local checkpoints. The 9800X3D workstation is not assumed to be the home server.

## Existing benchmark research

**Observed — upstream documentation, checked 2026-10-10:** [Home Assistant Datasets](https://github.com/allenporter/home-assistant-datasets) uses Synthetic Home and Home Assistant conversation agents. `assist-mini` is aimed at smaller models; `assist` tests harder actions; `questions` covers state questions but is under development; `automations` includes executable tests. It can run local model agents. Its standard results do **not** directly measure an external ha-mcp client. [Evaluation guide](https://github.com/allenporter/home-assistant-datasets/blob/main/docs/eval.md); [published reports](https://github.com/allenporter/home-assistant-datasets/blob/main/reports/README.md).

**Observed — upstream documentation, checked 2026-10-10:** The [ha-mcp in-process server](https://github.com/homeassistant-ai/ha-mcp/blob/master/docs/in-process-server.md#chat-with-the-toolset-from-home-assistant-conversation-agents--voice) can expose its toolset as a Home Assistant LLM API for conversation agents. It offers compact tool search and a full catalog. An integration with Home Assistant Datasets may be possible in a synthetic instance, but compatibility with that harness has **not** been tested. Do not add a second ha-mcp server to production for this.

**Observed — upstream documentation, checked 2026-10-10:** [MCP-Bench](https://github.com/Accenture/mcp-bench) tests generic MCP tool discovery and multi-step use, but its published tasks do not establish Home Assistant correctness. [SWE-bench Verified](https://github.com/SWE-bench/SWE-bench) and the [Aider Polyglot benchmark](https://github.com/Aider-AI/aider/blob/main/benchmark/README.md) are coding references; their full suites are much larger than the first budget-conscious screening round. Sampling them changes what any published score means.

**Observed — upstream documentation, checked 2026-10-10:** OpenRouter's [Pareto Router](https://openrouter.ai/docs/guides/routing/routers/pareto-router) is `openrouter/pareto-code`, is tuned for coding, changes its shortlist over time, and returns the actual selected model in the response. The [Models API](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties) can discover current model IDs, price, context length, and supported parameters; [tool-calling documentation](https://openrouter.ai/docs/guides/features/tool-calling) says to check tool support. Do not use Pareto Code as a proxy for Home Assistant ability without a separate evaluation.

**Observed — upstream documentation, checked 2026-10-10:** [FreeToken quick start](https://github.com/FlashML-org/FreeToken/blob/main/docs/quickstart.md) documents `/v1/models`, OpenAI-compatible `/v1/chat/completions` and `/v1/responses`, and Anthropic-compatible APIs. Its [install guide](https://github.com/FlashML-org/FreeToken/blob/main/docs/install.md) lists Linux/NVIDIA driver requirements. API compatibility does not prove a given checkpoint reliably emits tool calls; preflight it.

## High-value task patterns from this conversation

These are **Planned** sanitized task ideas, not a copied production dataset:

1. Find the correct coordinator entity among similarly named raw HVAC heads, room thermostats, and helpers.
2. Explain why a head remains active when a room sensor reads above a displayed number; inspect target, drift, hysteresis, mode, and freshness before concluding.
3. Detect an unavailable room sensor and propose a safe temporary fallback while stating its limitations.
4. Diagnose apparently matching lamp telemetry that disagrees with what the owner sees; avoid claiming a fix until the owner confirms physical appearance.
5. Make one bounded dashboard or automation change in a synthetic home, preserve unrelated settings, and demonstrate rollback.
6. Solve a small coding bug in a disposable repository, run meaningful tests, and explain the change and limits.

Include at least one task whose correct answer is to **make no change** and one with ambiguous evidence that requires a precise question or a bounded read-only check. Grade unsupported certainty as a failure.

## Next agent's first checks

- Confirm the owner's maximum spend before running paid evaluations.
- Recheck current OpenRouter catalog/prices/tool support and decide how to snapshot candidate selection before running.
- Check local GPU driver and memory, then FreeToken availability and a single tool-call smoke test; do not install or download huge models as an incidental planning step.
- Select the fixed task set and outcome-based graders before any paid run.
- Decide whether to adapt Home Assistant Datasets through ha-mcp's LLM API or use an external MCP client with a synthetic Home Assistant instance. Do not assume they are interchangeable.

## Follow-up — 2026-10-10

**Reported:** The owner prefers a capped OpenRouter API key as the spending guard; dynamic harness-side shutdown is optional. Pi and a small Python runner are both under consideration. The first test cases should be the strawberry letter-count and 50-meter car-wash questions. For HA tasks, the owner wants a mock that makes no real requests and asked to inspect upstream ha-mcp tests and fixtures first.

**Observed — repository inspection, 2026-10-10:** The first two cases and an offline grader now exist in [`tasks/smoke.json`](../tasks/smoke.json) and [`smoke.py`](../smoke.py). See the [upstream ha-mcp test review](upstream-ha-mcp-review.md) for findings from a pinned public checkout. No model calls or Home Assistant connections were made in that follow-up.

**Observed — upstream documentation review, 2026-10-10:** A [framework review](benchmark-framework-review.md) recommends a local Promptfoo proof of concept for the comparison matrix and visual report, with Inspect AI as an alternative if agent/coding tasks need stronger Python primitives. Neither framework has been installed or tested here.

## Promptfoo smoke follow-up — 2026-10-10

**Reported:** The owner selected Promptfoo for the first experiment layer and reported an OpenRouter workspace cap of $20/week. For the first paid smoke run, the stop condition is two model requests, one per pinned task, with no intentional retries. A dedicated key and its active limit have not yet been verified.

**Observed — local run:** Promptfoo `0.124.1` was pinned in `package.json` and `package-lock.json`. `npm run smoke` passed both tasks with a deterministic synthetic provider; the local HTML and JSON reports were written under ignored `artifacts/`. The run made no model or Home Assistant request. `OPENROUTER_API_KEY` was absent from the shell. No FreeToken or other local model process was observed, and the GPU driver check still failed. Model scores, tool behavior, and actual spend remain **Unknown**.

**Reported:** The owner selected the newest GLM Flash model for the first hosted run. **Observed — OpenRouter catalog checked 2026-10-10:** The [GLM Flash Latest alias](https://openrouter.ai/~z-ai/glm-flash-latest) points to [GLM 5.3 Flash](https://openrouter.ai/z-ai/glm-5.3-flash). The paid configuration pins `z-ai/glm-5.3-flash`, and `npm run smoke:openrouter` refuses to start without a key and an explicit $20/week cap confirmation. At this setup stage, the configuration validated offline and no hosted request had yet been sent.

**Observed — hosted smoke run, 2026-10-10:** The owner provided the key in the ignored `.env`. A single two-case run completed for `z-ai/glm-5.3-flash`. Promptfoo's strict grader scored 0/2 because its adapter prepended separate reasoning text; the final answer in each response matched the expected answer. Total reported OpenRouter charge was $0.00012909. The [run report](first-hosted-smoke.md) records full settings, hashes, and limits. The config was then changed to hide reasoning from the scored output.

**Observed — corrected verification run, 2026-10-10:** A second two-case run with `showThinking: false` passed both strict assertions. It recorded 224 tokens, 3281 ms run duration, and $0.00008309 reported account charge. Across both hosted runs, four requests cost $0.00021218 by Promptfoo's reported OpenRouter charges. The [run report](first-hosted-smoke.md) preserves both results. No HA or coding task has been evaluated.

## Local FreeToken follow-up — 2026-10-10

**Reported:** The owner said FreeToken was running on localhost with a Qwen 3.6 variant and asked for a configurable local benchmark path.

**Observed — live preflight and run:** `/v1/models` returned one served ID, `Qwen3.6-35B-A3B-heretic-NVFP4-MTP-FTW`. The ignored `.env` holds the local base URL and ID. `npm run smoke:local` uses the same two tasks and grader through a loopback-only OpenAI-compatible provider, with no hosted-key fallback. It passed strawberry (`3`) and failed car wash (`WALK`): 1/2, 655 tokens, about 50 seconds. See [the local run report](first-local-smoke.md). FreeToken version, hardware use, and tool-call support remain **Unknown**.

## First synthetic Home Assistant MCP follow-up — 2026-10-10

**Observed — upstream inspection:** [Synthetic Home](https://github.com/allenporter/home-assistant-synthetic-home) loads YAML areas, devices, and entities into a Home Assistant integration; it is not an MCP server. The fictional [North Room fixture](../fixtures/ha/north-room.yaml) was accepted by the pinned `synthetic-home==5.0.3` parser. This does not verify live Home Assistant state or service behavior.

**Observed — local run:** Promptfoo now runs a bounded read-only MCP agent against that fixture. The FreeToken Qwen variant called `ha_search`, then `ha_get_state` for the correct coordinator, and answered `70`: 1/1, three model requests, two MCP calls, 2,226 reported tokens, 6.9 seconds. The offline loopback stub also passed the whole harness path. See [the HA run report](first-ha-local.md). The original Promptfoo OpenAI MCP adapter only returned its first tool result without a follow-up model turn, so a small custom provider handles the agent loop.

**Planned:** For write tasks, run the actual Synthetic Home integration and ha-mcp inside an isolated Home Assistant instance. Do not point this benchmark at production. Matching real Home Assistant state attributes and full ha-mcp responses remains **Unknown**.

**Reported — owner direction, 2026-10-10:** Chained operations are the primary HA benchmark use case. Run real ha-mcp in Docker against a disposable Synthetic Home instance for write tests, and use that same path for substantive read-only HA cases. The narrow fake MCP fixture is only an agent-loop smoke test. See [the container benchmark design](ha-container-benchmark.md).

## Agent instruction benchmark follow-up — 2026-10-10

**Reported:** The owner wants two separate cases based on an earlier request: infer or clarify which rule belongs in user-wide versus project instructions, and independently consult the active agent harness's documentation to locate its effective user-wide instructions. This discovery test must work for whichever harness is running, not assume Codex.

**Planned:** Two fictional, unrun cases are pinned in [`tasks/agent-instructions.json`](../tasks/agent-instructions.json) and explained in [the instruction benchmark design](agent-instruction-benchmarks.md). They need an isolated filesystem agent runner and a profile-specific documentation source before model evaluation.

## Inspect AI pilot follow-up — 2026-10-10

**Reported:** The owner wants to pilot Inspect AI as a possible Promptfoo replacement, with a custom dashboard eventually. They endorsed a purpose-built Dockerfile with the benchmark tools.

**Observed:** Inspect AI `0.3.278` ran the two existing smoke cases against local FreeToken (1/2) and a small disposable coding repair (pass). The coding case passed again with the new unprivileged Docker image. The ignored `.eval` logs supplied per-sample score, model usage, timing, response model, and tool events; a small exporter writes normalized summary JSON. See [the pilot report](inspect-pilot.md). No paid or production HA call was made. HA and instruction-harness paths remain untested in Inspect.
