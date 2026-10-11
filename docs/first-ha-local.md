# First synthetic Home Assistant MCP run — 2026-10-10

## What was tested

**Observed — public source inspection, 2026-10-10:** [Synthetic Home](https://github.com/allenporter/home-assistant-synthetic-home) is a Home Assistant custom integration that loads YAML inventory to create areas, devices, and entities. It is not itself an MCP server. Its climate platform stores current and target temperatures and can respond to Home Assistant climate service calls. [ha-mcp](https://github.com/homeassistant-ai/ha-mcp) provides the separate MCP interface. The fake server in this repository implements a deliberately narrow read-only approximation of `ha_search` and `ha_get_state` using the same YAML inventory; it does not claim full ha-mcp compatibility.

**Observed — local parser check, 2026-10-10:** `synthetic-home==5.0.3` loaded [`north-room.yaml`](../fixtures/ha/north-room.yaml) and produced one area, two devices, and three entities. This checks the inventory parser, not Home Assistant startup or its rendered entity states. The fixture is fictional and contains no copied production identifiers.

**Planned:** For tasks that change state, start a separate Home Assistant instance with this integration and run real ha-mcp against that isolated instance. Then grade resulting HA state and service effects. The present fake MCP server is enough to screen read-only entity discovery and answer behavior, but cannot prove real HA service semantics, automations, integration behavior, or ha-mcp's full response contract.

## Pinned case and setup

The one task asks for the North Room Coordinator target temperature. The coordinator is set to 70°F and the similarly named raw indoor head is set to 74°F. A correct run must read `climate.north_room_coordinator` through `ha_get_state` and answer `70` exactly. There are no write tools.

| Setting | Value |
|---|---|
| Fixture SHA-256 | `38e1c8afedd739230dbe482e2ddd33ebedc284f67f0943af9ea1ea24e3db3a84` |
| Task SHA-256 | `2a1c2864be0541aca21913575baf58592edd1335465c7e577e692e9e180537cf` |
| Agent provider SHA-256 | `f546cd0200edd4b20a46f22f3b1ec891f0bb505e87bdefa337820adc13290d97` |
| MCP mock SHA-256 | `b63e59323d738ecef0acfa71761769a0f487df90ba44c7716f65a4b4042cb376` |
| Grader SHA-256 | `d5a637b90fa956e8b6fa528fe8a1148830bd0373153e29b321a36c48b940f99a` |
| Promptfoo | `0.124.1` |
| MCP SDK | `1.32.1` |
| Synthetic Home parser | `5.0.3` |
| Provider/runtime | Local OpenAI-compatible FreeToken; exact FreeToken build **Unknown** |
| Requested and returned model | `Qwen3.6-35B-A3B-heretic-NVFP4-MTP-FTW` |
| Inference | temperature 0, max 512 output tokens per request, tool choice auto |
| Limits | one case, one repeat, four model requests, four tool calls, one concurrent run |
| Cache and sharing | disabled |

## Result

**Observed — local run, 2026-10-10:** The model called `ha_search` for North Room Coordinator, then `ha_get_state` for `climate.north_room_coordinator`, then answered `70`. The answer and required state read passed the deterministic grader: **1/1**. Promptfoo reported three model requests, 1,807 prompt tokens, 419 completion tokens, 2,226 total tokens, and 6,949 ms provider latency. Hosted charge was $0; local electricity and hardware cost are **Unknown**. The ignored raw report is at `artifacts/promptfoo-ha-local.html` and its JSON companion.

**Observed — offline harness verification, 2026-10-10:** A deterministic loopback chat stub completed search → state → answer through the same provider and MCP server. This checks orchestration only and is not counted as a model result.

**Observed — earlier adapter probe, 2026-10-10:** Promptfoo's built-in OpenAI MCP adapter executed the first tool call but returned its result as the evaluated output without continuing the conversation. That failed the pinned case. The small provider in [`ha-local-agent.cjs`](../providers/ha-local-agent.cjs) now runs the bounded follow-up turns while Promptfoo retains its task table, grader, and report.

**Unknown:** Whether the same fixture produces identical state attributes under a running Home Assistant integration; whether the model's 1/1 result repeats; and whether broader or write tasks succeed. A single read-only case does not establish general Home Assistant ability.

## Live contract check and next implementation step

**Observed — production ha-mcp, read-only inspection, 2026-10-10:** A targeted climate search returned entity records with `entity_id`, `friendly_name`, and `state`, plus pagination, partial-result, error, and warning fields in the response. A targeted `ha_get_state` call returned a `data` record and `metadata`; its climate attributes included `temperature`, `current_temperature`, `hvac_action`, `hvac_modes`, and `supported_features`. Only these field names and response shapes were retained. Live IDs, names, values, and raw responses were not copied into this repository.

**Observed — implementation review, 2026-10-10:** The current fake `ha_search` response uses `name` instead of `friendly_name` and omits several real response fields. Its one-case pass therefore tests tool discovery and a bounded conversation against an approximation, not exact ha-mcp behavior. Extending this imitation field by field would be brittle.

**Planned — revised after owner feedback, 2026-10-10:** Use real ha-mcp against a disposable Home Assistant instance running Synthetic Home for chained read and write cases alike. Reserve the handwritten fake for the cheap agent-loop smoke test. Fresh HA state per case is safer and more reproducible than undoing individual writes. [Upstream ha-mcp's end-to-end tests](https://github.com/homeassistant-ai/ha-mcp/tree/master/tests/src/e2e) already use an isolated HA container; adapt that boundary rather than growing the fake response layer. The container design is in [the benchmark plan](ha-container-benchmark.md).
