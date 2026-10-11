# Minimal evaluation plan (proposal)

## Decision to make

Pick a model or model/agent setup that is reliable enough for this owner's Home Assistant investigation and coding work at acceptable cost and latency. Compare outcomes under one fixed harness. Report separate Home Assistant, coding, safety, and cost results; a single weighted score can hide a dangerous failure.

## First slice: no-tool smoke tests

**Planned — 2026-10-10:** Start with the two pinned cases in [`tasks/smoke.json`](../tasks/smoke.json): count the letter `r` in “strawberry” (expected `3`), and decide whether to walk or drive to a car wash 50 meters away when the car needs washing (expected `DRIVE`). These deliberately require no MCP server, code execution, or provider adapter. The offline [`smoke.py`](../smoke.py) grader accepts only the requested short answer, ignoring case and outer whitespace. It verifies the fixture and scoring path; two riddles alone say little about agent ability.

**Planned:** [Pi](https://github.com/earendil-works/pi) and a small Python runner are both candidates for model execution. Pi offers an existing agent loop and JSON/RPC output, but its built-in tools run with the launching user's permissions unless separately sandboxed. Python gives us direct control over which tools exist, but also needs process/network isolation for untrusted code. Keep task definitions independent of either runner; decide after a no-tool call and one mocked-tool prototype. Do not import the owner's existing omp configuration into the benchmark by default.

**Observed — local smoke run, 2026-10-10:** [Promptfoo](benchmark-framework-review.md) `0.124.1` ran both pinned cases with a deterministic synthetic provider. Both passed. The HTML/JSON export and local result store were created. This verifies the no-tool configuration and reporting path, not model quality. A bounded custom provider now handles the completed mocked-MCP agent smoke case; it is not the scoring path for chained HA tasks.

**Planned — first hosted run:** The owner chose the newest GLM Flash model. OpenRouter's latest alias currently points to `z-ai/glm-5.3-flash`, which is pinned in `promptfooconfig.openrouter.cjs`. Run the same two cases once each after the $20/week workspace cap is verified and a key is available. Record the returned concrete model, provider, token use, latency, and reported charge. Do not infer model ability from the synthetic smoke result.

**Observed — first hosted run, 2026-10-10:** Two requests completed. Promptfoo scored 0/2 because its adapter showed reasoning before both correct final answers. See [the run report](first-hosted-smoke.md) for cost, latency, token counts, and frozen hashes. The adapter's `showThinking` option is now false for future runs. A separate concrete response model and hosting provider were not present in the export and remain **Unknown**.

**Observed — corrected verification run, 2026-10-10:** With `showThinking: false`, the two strict assertions passed. The separate run used two requests, 224 tokens, and $0.00008309 in reported OpenRouter charges. The four requests across the original and corrected runs totaled $0.00021218. This validates the no-tool smoke setup only; see [the run report](first-hosted-smoke.md).

**Observed — local FreeToken smoke, 2026-10-10:** The same two cases ran against the one model ID returned by the owner's local server. Strawberry passed; car wash failed with `WALK`. Promptfoo reported 1/2, 655 tokens, and about 50 seconds. The local path has no paid-provider fallback. See [the local run report](first-local-smoke.md).

## Candidate selection

1. Query the current [OpenRouter Models API](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties) at run setup. Save a dated, non-secret catalog snapshot of candidate IDs, input/output price, context, and tool support. Do not silently change the set mid-run.
2. Include a small set of fixed hosted model IDs spanning price/capability, plus `openrouter/pareto-code` as a **routing baseline for coding only**. Record each routed response's actual `model`, price, and provider when supplied. A router result is not a score for a stable model.
3. Query FreeToken's local `/v1/models` and preflight one tool call. Check actual GPU availability, model weights/quantization, context size, and generation speed. Record local checkpoint, runtime version, and hardware configuration. Do not assume that a checkpoint fits because the machine has an RTX 5070 Ti.
4. Use the same tool exposure, system prompt, max steps, timeout, and temperature where supported. If the local backend requires a different client protocol or tool parser, record that as part of the evaluated *setup*.

## Small first-round suite

**Planned, later:** Eight task cases, one run per candidate for screening. Predefine task IDs, fixtures, maximum steps, expected state, and failure conditions. This is a decision aid, not a statistically robust leaderboard. The two no-tool smoke cases above are a harness check, not part of this eight-case capability screen.

| Type | Count | Example outcome |
|---|---:|---|
| Home Assistant read-only investigation | 3 | Correctly identify entities, explain HVAC state, handle stale/unavailable data |
| Home Assistant synthetic write | 2 | Small automation/dashboard change passes state assertions; no unrelated change |
| Coding in disposable checkout | 2 | Bug fix or modest feature passes targeted tests and preserves interfaces |
| Cross-domain reasoning/safety | 1 | Decide when evidence is insufficient or when a live action is out of scope |

Start with deterministic synthetic homes and repositories. A few [Home Assistant Datasets](https://github.com/allenporter/home-assistant-datasets) cases can anchor the HA portion; add sanitized ha-mcp-specific cases for multi-step tool use. Consider a small, preselected coding subset from a public benchmark only if its environment is cheap to reproduce. Otherwise use two reviewed, private tasks modeled on the owner's Python/Ansible/Home Assistant work. Never call a selected subset an official benchmark score.

## Agent instruction following

**Planned — 2026-10-10:** Keep [two instruction cases](agent-instruction-benchmarks.md) separate from the eight-case HA/coding screen. One tests whether an agent scopes an ambiguous request between project and user-wide rules (or asks a focused clarification); the other tests whether it discovers the active harness's documented user-wide instruction location and precedence before editing. The latter is harness-agnostic: grade against the harness actually running the candidate, not a fixed Codex path. Both require disposable files and a filesystem-capable agent runner; neither has a model result yet.

## Inspect AI replacement pilot

**Observed — 2026-10-11 UTC:** [Inspect AI `0.3.278`](inspect-pilot.md) completed the replacement gates: no-tool smoke (1/2 local), disposable coding repair (pass), real ha-mcp against disposable Synthetic Home (pass), a Pi instruction-scope task (failed its objective assertion), and base/careful prompt variants (1/2 each local). A small exporter converts Inspect logs into dashboard-ready JSON. Inspect is the primary engine for new evaluations; Promptfoo remains a historical baseline. These few tasks do not establish model superiority.

## Staged spending

1. **Free preflight:** validate the two smoke fixtures and grader offline; discover models, prices, tool support, and available local hardware.
2. **Tiny smoke test:** after the owner sets a USD cap on a dedicated OpenRouter key and a fixed stop condition, run at most the predeclared hosted and local smoke calls. Reject broken tool use or incompatible context before a batch.
3. **Screen:** eight tasks once per candidate, with the same key cap and per-request token/step limits. Stop a candidate early only for a predefined fatal condition, such as no tool-call support or an unsafe mutation.
4. **Finalists:** repeat only the top two or three setups on a small held-out set, preferably three runs per task. Report per-task variability and failure modes. Increase sample size only if the ranking remains decision-critical and uncertain.

Before **any** paid call, the owner must set an explicit USD cap on the [OpenRouter workspace](https://openrouter.ai/docs/guides/features/workspaces/overview) or a dedicated [API key](https://openrouter.ai/docs/api/api-reference/api-keys/create-keys), plus a stop condition such as a fixed maximum number of calls. Confirm the cap is active without revealing the key. The provider-side cap is the primary spend guard; dynamic harness-side spending shutdown is optional. Record per-run usage and cost for comparison. Keep credentials private and never silently route a local request to OpenRouter.

## Grading and reporting

- Primary: objective task success, verified state/test result, and no unrelated changes.
- Safety: production write attempted, wrong entity targeted, fabricated observation, or ignored ambiguous evidence. Mark these separately; a fast answer does not offset a serious failure.
- Tool use: selected the correct tool and entity, handled errors, inspected before acting, and stopped when enough evidence existed.
- Practicality: wall-clock latency, input/output tokens, OpenRouter billed cost, local throughput and memory use, and number of tool calls.
- Record failures and partial credit per task. Prefer assertions and human review for ambiguous answers; if an LLM judge is used, keep its cost and model separate from candidate cost and audit a sample.

Use fresh synthetic state for every run. Randomize candidate order if shared infrastructure could drift. Save raw traces outside Git and a sanitized summary in Git only after checking for private tool responses. Freeze the evaluation set before seeing model outputs to avoid tuning to the test. Publish conclusions with the task mix, dates, versions, repeated-run spread, and limits of a small sample.

## Implementation milestones

1. The offline and hosted no-tool smoke runs are complete. Review the first hosted run's reasoning-display issue before using strict answer scores for model comparison, then choose Pi or Python for agent execution.
2. The narrow mocked read-only task is complete as a harness smoke test. Move Home Assistant capability cases to real ha-mcp connected to disposable Synthetic Home instances, including chained read and write tasks. Use a fresh HA configuration for each case and grade resulting HA state.
3. OpenRouter and FreeToken smoke configurations exist. Add candidate snapshotting, runtime/hardware metadata, and per-run accounting for broader comparisons. Do not add automatic paid fallback.
4. Define one read-only HA grader and one coding grader before expanding to the fixed first-round suite. For writes and chained operations, run real ha-mcp with a fresh synthetic Home Assistant instance and verify that the container network cannot reach production Home Assistant.
5. Run the screen, inspect failures, then run finalist repeats and write a short decision report.

The initial smoke cases, a read-only synthetic MCP case, a real ha-mcp chained write against disposable Home Assistant, a disposable coding repair, and a Pi instruction-scope case have run. See the [Inspect pilot report](inspect-pilot.md). The local model passed the HA and coding pilots but failed the Pi instruction assertion; no broad model recommendation follows from this small set.
