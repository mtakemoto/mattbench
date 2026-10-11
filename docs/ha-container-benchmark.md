# Real ha-mcp with disposable Synthetic Home

## Decision

**Reported — owner direction, 2026-10-10:** Chained Home Assistant operations are the main use case. Use real ha-mcp in Docker for write tests, connected to a disposable synthetic Home Assistant instance. Apply the same path to substantive read-only HA cases so tool behavior is comparable.

**Observed — upstream and local review, 2026-10-10:** [ha-mcp's end-to-end tests](https://github.com/homeassistant-ai/ha-mcp/blob/master/tests/README.md) start a real Home Assistant container and exercise the actual MCP server. Its [Docker Compose example](https://github.com/homeassistant-ai/ha-mcp/blob/master/docker-compose.yml) points ha-mcp at Home Assistant by service name. [Synthetic Home](https://github.com/allenporter/home-assistant-synthetic-home) loads a YAML inventory into real HA entities. Docker Engine 29.8.1 and Compose 5.5.1 are available on this workstation. The Inspect pilot subsequently ran real ha-mcp through Docker stdio against disposable Synthetic Home and changed only a fictional coordinator.

## Target execution path

1. Stage a fresh Home Assistant configuration in an ignored per-run directory and load a pinned, fictional Synthetic Home inventory. Bootstrap a test-only account and token at runtime; no token or auth database belongs in Git.
2. Start pinned Home Assistant and ha-mcp images on a dedicated internal Docker network. ha-mcp's Home Assistant URL must resolve only to the synthetic service. Do not mount production configuration, pass production credentials, or expose either service publicly.
3. Connect the benchmark agent to that real ha-mcp container through a controlled MCP transport. Pin the exposed tool subset, prompt, model settings, request limit, and step limit for the task.
4. Run the chained task. Grade final HA state and absence of unrelated changes through a separate test-control path. Record the tool sequence, token use, latency, model/runtime, and image and fixture versions.
5. Stop and remove both containers and their per-run state in a `finally` cleanup path. Start from a fresh configuration for the next case, even after a failure.

Destroying the per-run state is the reset. Undoing only visible entity changes could leave altered automation definitions, entity registries, events, history, or caches and would make later scores order-dependent.

## First case and boundaries

**Implemented — 2026-10-11:** `tasks/inspect-ha-cases.json` pins two fictional cases: turn off a Study Reading Lamp while its Desk Lamp remains on, and set a North Room MXZ-style Coordinator target to 68 °F while its raw Indoor Head remains at 74 °F. The shared runner starts a fresh internal Docker network, Synthetic Home, and ha-mcp for each case, validates initial state, runs Inspect with a ten-turn limit and three MCP tools, then removes both containers and the network. The grader checks pinned final states and the Inspect message trace: every service call must match the allowed action and target, required search and initial reads must precede the write, and both entities must be read back afterward. This catches an unintended service call even if its state change is later undone. It does not prove physical device safety or cover writes outside the exposed tool subset.

The integration simulates supported entity state and service methods. It does not simulate a Mitsubishi controller, physical heating dynamics, sensor freshness from real hardware, or all integration-specific automations. Those limitations belong in case descriptions and scoring.

## Console suite behavior

**Implemented — 2026-10-11:** The console's default All cases job runs the two pinned smoke tasks together, then each HA case in `tasks/inspect-ha-cases.json` sequentially. Smoke uses the base prompt. Each HA case starts its own fresh Synthetic Home and ha-mcp containers on a new internal network, and teardown runs before the next case begins. With the current two HA cases, the configured maximum is 22 model calls: two smoke calls and ten per HA case. The suite is limited to FreeToken and private compatible endpoints; OpenRouter remains available for individually selected smoke runs only.

The job status reports its phase, current case, completed case IDs and evaluator-process outcomes, completed count, total count, and a user-facing message. If an evaluator process fails, the runner records that outcome and continues through the remaining cases. A successful evaluator process can still receive a failing model score; process outcome and task score are separate. After the suite ends, any failed case process makes the overall job failed while preserving completed case results. A failure before or during suite orchestration also ends the job as failed. The job is complete only after the Inspect summary export succeeds.

## Measured reset overhead

**Observed — 2026-10-11:** Each deterministic preflight began from a fresh configuration, checked pinned initial states, connected through the pinned ha-mcp container's stdio transport, called `ha_call_service`, read both entities through `ha_get_state`, checked pinned final states, then removed the containers and network. On warm images with cached Synthetic Home source, lamp setup took 4.357 s, MCP interaction 1.592 s, and cleanup 0.281 s. The MXZ-style coordinator setup took 4.392 s, MCP interaction 11.358 s, and cleanup 0.425 s. The earlier direct-HA fixture preflight measured setup at 5.557 s and 5.202 s. These are individual observations on this workstation, not a stable benchmark distribution, and exclude model generation. The ignored `artifacts/inspect/ha-timing/*.json` records setup, evaluation, cleanup, and total wall time for future agent runs; the summary exporter joins those metrics to Inspect results by eval ID. No model-scored run of these new case definitions occurred because the configured FreeToken endpoint refused connections during verification.

**Observed — 2026-10-11:** The pinned Synthetic Home integration source is cached under ignored artifacts after the first download. The HA and ha-mcp images are local; the benchmark network is internal. The prior climate pilot proved `docker exec` stdio with the complete Inspect agent loop. The new lamp and manifest-driven climate cases still need model-scored end-to-end runs when FreeToken is available.

## Remaining limits

- The deterministic preflight proves real ha-mcp service and state tools, fixture loading, and final-state assertions. It does not score the new cases with model-generated tool choices; that remains to run when FreeToken is available.
- Synthetic Home does not model Mitsubishi physical dynamics or integration-specific behavior. The MXZ-style case measures entity choice, service use, and readback.
- Run timing is machine and cache dependent. Compare setup and cleanup distributions over repeated runs before deciding that per-case isolation is too expensive.

The existing handwritten MCP fixture remains a low-cost harness test. It is not the scoring path for chained or write capability comparisons.
