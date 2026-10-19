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

**Implemented — 2026-10-11; updated 2026-10-12 UTC:** `tasks/inspect-ha-cases.json` pins two fictional cases: turn off a Study Reading Lamp while its Desk Lamp remains on, and set a North Room MXZ-style Coordinator target to 68 °F while its raw Indoor Head remains at 74 °F. The shared runner starts a fresh internal Docker network, Synthetic Home, and ha-mcp for each case, validates initial state, runs Inspect with a twelve-generation limit and three MCP tools, then removes both containers and the network. The grader checks pinned final states and the Inspect message trace: every service call must match the allowed action and target, required search and initial reads must precede the write, and both entities must be read back afterward. It accepts ha-mcp's documented target placement at either the top level or inside service data. This catches an unintended service call even if its state change is later undone. It does not prove physical device safety or cover writes outside the exposed tool subset.

**Implemented — 2026-10-12 UTC:** Trace acceptance now correlates unique tool-call IDs with successful result messages. Search must actually return a relevant expected entity, not merely echo the query. Required initial observations must complete before the write request; a successful write result must precede separate successful readback requests whose returned states match the expected entities. Missing, malformed, failed, unrelated, or batched out-of-order results do not establish these observations. Every attempted service call is checked for its action and target, including attempts that fail.

Single-entity projections use the correlated request identity when `fields` explicitly excludes `entity_id`. Bulk projected records use the keys of the returned `states` map; a returned `entity_id`, when present, must still match. A bulk `success=True` does not hide a missing or malformed required record. The grader supports both documented shapes without accepting reads requested before write completion.

The integration simulates supported entity state and service methods. It does not simulate a Mitsubishi controller, physical heating dynamics, sensor freshness from real hardware, or all integration-specific automations. Those limitations belong in case descriptions and scoring.

## Console suite behavior

**Implemented — 2026-10-11; updated 2026-10-12 UTC:** The console's default All cases job runs the two pinned smoke tasks together, then each HA case in `tasks/inspect-ha-cases.json` sequentially. Smoke uses the base prompt. Each HA case starts its own fresh Synthetic Home and ha-mcp containers on a new internal network, and teardown runs before the next case begins. With the current two HA cases, the configured maximum is 26 model generations: two smoke calls and twelve per HA case. FreeToken, OpenRouter, and private compatible endpoints are available. OpenRouter runs require confirmation of the owner-reported workspace dollar cap, and the app collects per-generation billed cost afterward through OpenRouter's read-only API.

The call ceiling is derived from the validated smoke fixture and HA manifest, then saved in an immutable execution-plan snapshot for the run. Request confirmation must match that plan exactly before discovery or launch. Editing a fixture after launch cannot change the selected inputs or expand the confirmed allowance. Model API, sample-error, and task retries are disabled.

The job status reports its phase, current case, completed case IDs and evaluator-process outcomes, completed count, total count, and a user-facing message. If an evaluator process fails, the runner records that outcome and continues through the remaining cases. A successful evaluator process can still receive a failing model score; process outcome and task score are separate. After the suite ends, any failed case process makes the overall job failed while preserving completed case results. A failure before or during suite orchestration also ends the job as failed. The job is complete only after the Inspect summary export succeeds.

The detached Python worker retains the single-run lock through billing, summary export, and terminal publication, including across console restarts. Setup, evaluation, and cleanup have independent 240-, 180-, and 40-second deadlines. State reads and Docker commands are also bounded; cancellation terminates child process groups before independent removal attempts. Cleanup and progress-publication failures preserve the original evaluation/setup failure. Timing files are atomically replaced. **Observed — 2026-10-12 UTC:** Offline regressions exercised process-group termination, cancellation, cleanup failure handling, and worker ownership. **Unknown:** These revised failure paths have not been exercised against live Docker during this review-fix task.

## Measured reset overhead

**Observed — 2026-10-11:** Each deterministic preflight began from a fresh configuration, checked pinned initial states, connected through the pinned ha-mcp container's stdio transport, called `ha_call_service`, read both entities through `ha_get_state`, checked pinned final states, then removed the containers and network. On warm images with cached Synthetic Home source, lamp setup took 4.357 s, MCP interaction 1.592 s, and cleanup 0.281 s. The MXZ-style coordinator setup took 4.392 s, MCP interaction 11.358 s, and cleanup 0.425 s. The earlier direct-HA fixture preflight measured setup at 5.557 s and 5.202 s. These are individual observations on this workstation, not a stable benchmark distribution, and exclude model generation. The ignored `artifacts/inspect/ha-timing/*.json` records setup, evaluation, cleanup, and total wall time for future agent runs; the summary exporter joins those metrics to Inspect results by eval ID. At that date, no model-scored run of the new case definitions had occurred because the configured FreeToken endpoint refused connections.

**Observed — 2026-10-12 UTC:** A model-scored OpenRouter GLM 5.3 Flash run exercised both cases through the full path. See the [run and scaling report](glm-flash-suite.md). Both final synthetic states matched, but the strict trace scorer rejected earlier wrong or untargeted service calls. The five deterministic preflights and two model runs measured a 4.3–5.6 s setup range and about 0.3 s cleanup per case on this workstation. Fresh containers remain a reasonable default at the current suite size.

## Remaining limits

- The GLM run scores model-generated tool choices and the final synthetic state. A local FreeToken run of these exact cases remains unobserved.
- Synthetic Home does not model Mitsubishi physical dynamics or integration-specific behavior. The MXZ-style case measures entity choice, service use, and readback.
- Run timing is machine and cache dependent. Compare setup and cleanup distributions over repeated runs before deciding that per-case isolation is too expensive.

The existing handwritten MCP fixture remains a low-cost harness test. It is not the scoring path for chained or write capability comparisons.
