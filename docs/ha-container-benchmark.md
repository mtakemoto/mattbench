# Real ha-mcp with disposable Synthetic Home

## Decision

**Reported — owner direction, 2026-10-10:** Chained Home Assistant operations are the main use case. Use real ha-mcp in Docker for write tests, connected to a disposable synthetic Home Assistant instance. Apply the same path to substantive read-only HA cases so tool behavior is comparable.

**Observed — upstream and local review, 2026-10-10:** [ha-mcp's end-to-end tests](https://github.com/homeassistant-ai/ha-mcp/blob/master/tests/README.md) start a real Home Assistant container and exercise the actual MCP server. Its [Docker Compose example](https://github.com/homeassistant-ai/ha-mcp/blob/master/docker-compose.yml) points ha-mcp at Home Assistant by service name. [Synthetic Home](https://github.com/allenporter/home-assistant-synthetic-home) loads a YAML inventory into real HA entities. Docker Engine 29.8.1 and Compose 5.5.1 are available on this workstation, though the sandboxed process needed elevated Docker socket access. No benchmark containers have been started here.

## Target execution path

1. Stage a fresh Home Assistant configuration in an ignored per-run directory and load a pinned, fictional Synthetic Home inventory. Bootstrap a test-only account and token at runtime; no token or auth database belongs in Git.
2. Start pinned Home Assistant and ha-mcp images on a dedicated internal Docker network. ha-mcp's Home Assistant URL must resolve only to the synthetic service. Do not mount production configuration, pass production credentials, or expose either service publicly.
3. Connect the benchmark agent to that real ha-mcp container through a controlled MCP transport. Pin the exposed tool subset, prompt, model settings, request limit, and step limit for the task.
4. Run the chained task. Grade final HA state and absence of unrelated changes through a separate test-control path. Record the tool sequence, token use, latency, model/runtime, and image and fixture versions.
5. Stop and remove both containers and their per-run state in a `finally` cleanup path. Start from a fresh configuration for the next case, even after a failure.

Destroying the per-run state is the reset. Undoing only visible entity changes could leave altered automation definitions, entity registries, events, history, or caches and would make later scores order-dependent.

## First case and boundaries

**Planned:** A small climate sequence: discover the coordinator, read its target, set a new target through real ha-mcp, read it back, and verify the expected target in Home Assistant while the raw indoor head remains unchanged. Pin the exact initial and final values and allowed tool calls before any model run. Add an automation or dashboard task only after the service path and reset are working.

The integration simulates supported entity state and service methods. It does not simulate a Mitsubishi controller, physical heating dynamics, sensor freshness from real hardware, or all integration-specific automations. Those limitations belong in case descriptions and scoring.

## Implementation checks still open

- **Unknown:** A reproducible test-only onboarding/token bootstrap and Synthetic Home config-entry creation for a fresh HA container. Verify this with the pinned HA version before committing a Compose workflow. Avoid editing `.storage` directly as an ad hoc setup step.
- **Unknown:** Exact image digests, startup time, and whether Synthetic Home dependencies can be baked into the HA image so the runtime network stays isolated.
- **Unknown:** The best host-to-MCP transport for this workstation. A `docker exec` stdio path could avoid publishing a port; verify that it supports the complete agent loop.

The existing handwritten MCP fixture remains a low-cost harness test. It is not the scoring path for chained or write capability comparisons.
