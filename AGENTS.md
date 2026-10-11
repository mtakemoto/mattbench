# Agent guide

This is a planning repository. Read `README.md`, `docs/context-handoff.md`, and `docs/evaluation-plan.md` before implementing or running an evaluation.

## Evidence

Use **Observed** for facts inspected directly during the current task, **Reported** for owner statements, **Planned** for intended tests or architecture, and **Unknown** where verification is needed. Date live observations. Repository notes do not prove current Home Assistant, OpenRouter, or local runtime state.

## Safety and authority

- Benchmark against a synthetic Home Assistant instance for every task that writes state. Use the production ha-mcp connection only for explicitly authorized, read-only investigation. A connection is not permission to change the home.
- For chained or write benchmarks, use the real ha-mcp server connected to a disposable synthetic Home Assistant instance. Give each case a fresh test state; cleaning up selected entities after a run is not a reset. Keep the benchmark containers separate from production networks and credentials.
- The owner authorizes using the existing production ha-mcp connection for read-only investigation to shape benchmark fixtures and check real tool response formats. Inspect only what the task needs. Convert observations into fictional, sanitized test data; never commit raw responses, live entity IDs, private topology, or identifying values. Record the observation date and what was generalized.
- Never create a second production ha-mcp server or a second normal writer to HVAC entities. Check the existing connection before requesting setup steps.
- Never put OpenRouter keys, HA tokens, MCP connect URLs, private addresses, unredacted traces, or user data in Git. Do not print secrets in logs or chat.
- Treat model output as untrusted. A grader may read results; it must not execute arbitrary generated commands outside a sandbox.
- Pin task fixtures and scoring before comparing models. Record model ID, provider/runtime, concrete routed model, prompt/tool versions, inference settings, token use, latency, and cost for each run.
- Require an explicit dollar cap and stop condition before paid evaluation. Do not silently fall back from local FreeToken to a paid provider.
- Do not change the neighboring `homesvr-ansible` repository or the live home merely to make a benchmark pass.

## Project scope

Build the smallest reusable harness that supports Home Assistant MCP tasks and coding tasks. Prefer objective state/test assertions over an LLM judge. Keep a small held-out set and report uncertainty; a handful of tasks screens candidates but cannot establish broad model superiority.

## Implementation concerns

If an approach feels brittle or hacky, tell the owner immediately what is awkward, why it matters, and what cleaner alternative is worth researching. Research that alternative before extending the workaround. Continue safe, independent work while the decision is open.
