# ha-mcp test and fixture review — 2026-10-10

**Observed:** Inspected the public [`homeassistant-ai/ha-mcp`](https://github.com/homeassistant-ai/ha-mcp) repository at commit `b274a93b16cf96db2a4ecf4580c841f5072e6faf`. This review concerns upstream test code; it did not connect to any Home Assistant instance.

## Reusable pieces

- [Unit test setup](https://github.com/homeassistant-ai/ha-mcp/blob/b274a93b16cf96db2a4ecf4580c841f5072e6faf/tests/src/unit/conftest.py) puts ha-mcp configuration in temporary directories, disables its settings UI sidecar, backups, and update checks, and resets cached settings between tests. These isolation steps are worth adapting.
- [State-tool unit tests](https://github.com/homeassistant-ai/ha-mcp/blob/b274a93b16cf96db2a4ecf4580c841f5072e6faf/tests/src/unit/test_tools_get_states.py) register the real `ha_get_state` tool against a mocked Home Assistant client. This can test actual ha-mcp tool formatting and errors without HA requests.
- [End-to-end fixtures](https://github.com/homeassistant-ai/ha-mcp/blob/b274a93b16cf96db2a4ecf4580c841f5072e6faf/tests/src/e2e/conftest.py) start an isolated HA test container and create a real ha-mcp server and an in-memory FastMCP client. They also support separate HTTP and stdio paths. Their [baseline configuration](https://github.com/homeassistant-ai/ha-mcp/tree/b274a93b16cf96db2a4ecf4580c841f5072e6faf/tests/initial_test_state) and [basic connection assertions](https://github.com/homeassistant-ai/ha-mcp/blob/b274a93b16cf96db2a4ecf4580c841f5072e6faf/tests/src/e2e/basic/test_connection.py) are useful references for a later contract check.
- The upstream repository has an [MIT license](https://github.com/homeassistant-ai/ha-mcp/blob/b274a93b16cf96db2a4ecf4580c841f5072e6faf/LICENSE). Preserve its license notice if copying substantial fixture or test code.

## Fit for this benchmark

**Observed:** Upstream tests primarily assert that ha-mcp tools and transports behave correctly. They do not present a task to an agent and grade the agent's choice of tool, entity, or final answer. Its container baseline is broad and includes many integrations; copying it wholesale would make this small first slice harder to understand.

**Observed — 2026-10-10:** The tiny fake MCP surface was implemented and passed one local read-only smoke case. It exposed a real-contract difference: its search record uses `name` while live ha-mcp uses `friendly_name`. Keep it as a harness check only.

**Planned — revised after owner feedback, 2026-10-10:** Use upstream's disposable HA container pattern with actual ha-mcp for substantive read-only and chained write tasks. Start from a fresh synthetic HA state per case. This exercises real tool formatting, state changes, and multi-step behavior through the same path. See [the container benchmark design](ha-container-benchmark.md).

**Unknown:** The minimal reproducible setup for the disposable HA plus real ha-mcp benchmark, including test-only authentication and Synthetic Home config-entry creation. The mocked-client unit-test pattern remains useful for narrow regression tests, but is not the intended capability-scoring path.
