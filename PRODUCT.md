# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

SvelteKit, explicitly requested by the owner for this first app surface. The existing benchmark engine is Python/Inspect AI.

## Users

The owner is the primary user. They compare agent models and prompting strategies for their own Home Assistant MCP and coding tasks.

## Product Purpose

Run small, reproducible benchmarks and make model and prompt differences easy to inspect. A useful result shows task-level pass/fail, latency, tokens, tool behavior, and hosted cost without hiding safety failures behind one score.

## Operating Context

The owner has a local OpenAI-compatible FreeToken service and an OpenRouter workspace. They want future support for additional local ports, LAN endpoints, and other providers. Home Assistant write tests must run against disposable synthetic state through real ha-mcp.

## Capabilities and Constraints

- Choose a model from FreeToken or OpenRouter for a benchmark run. Treat endpoint profiles as an extensible concept so another OpenAI-compatible endpoint can be added later.
- Compare a base prompt with a revised prompt on the same pinned tasks. Show raw per-task outcomes and metadata, not only an aggregate.
- OpenRouter calls require an explicit dollar cap and maximum call count; local runs never fall back to a paid route.
- Store credentials, raw traces, and private values outside Git. Publish only sanitized summary data.
- The benchmark engine is Inspect AI. Promptfoo remains as a historical baseline after the replacement pilot.

## Brand Commitments

The owner asked for a bold, fun first visual direction and later specified “form and function, not sacrificing one for another.” The console should look and feel good without delaying the task or wasting space. The product name is currently mattbench; no external brand assets are supplied.

## Evidence on Hand

- Pinned smoke, HA, coding, and agent-instruction fixtures in this repository.
- Local Inspect `.eval` logs and a sanitized summary exporter.
- No representative multi-model result set yet; the UI must not imply a broad ranking from the pilot samples.

## Product Principles

1. Show the task result before any leaderboard number.
2. Make model, provider, prompt version, and run settings visible together.
3. Keep paid execution deliberately bounded and explicit.
4. Let new endpoint profiles fit the same run and report flow.
