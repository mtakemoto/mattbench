# Agent instruction benchmarks

**Reported — 2026-10-10:** The owner identified two separate failures worth testing: resolving which part of an ambiguous request belongs in user-wide versus project instructions, and independently finding the effective user-wide instruction file for the active agent harness. The second case applies to whichever harness runs the candidate, not only Codex.

**Planned:** The prompts and outcome criteria are pinned in [`tasks/agent-instructions.json`](../tasks/agent-instructions.json). They use a fictional staging catalog and disposable instruction files. Neither case needs Home Assistant or any live service.

## Cases

| Case | Capability | Full-credit result |
|---|---|---|
| `instruction_scope_ambiguous_reference` | Resolve an ambiguous “write this” using context | General implementation concern goes in user-wide and project instructions; project-only read permission stays project-scoped. Preserve existing content. |
| `discover_active_harness_global_instructions` | Discover the active harness's instruction mechanism | Identify the harness, consult its official instructions and runtime configuration, edit the effective user-wide file, and verify the result. |

For the scope case, a focused question about *which rule belongs where* is an acceptable safe response when the candidate cannot infer intent. Score it as clarification, separate from a completed edit. A generic “where is your main file?” question does not satisfy the discovery case when the path is discoverable from the active harness and its documentation.

## Runner and scoring requirements

**Planned:** Run each case in a disposable home and repository with pre-existing sentinel text in both instruction files. Record filesystem changes and a timestamped tool trace. Give the discovery case a harness profile that exposes its real runtime identity, configuration, and official documentation. The expected path and filename are profile-specific; do not put them in the candidate prompt. A Codex run, a Pi run, or another supported harness must be graded against *its own* documented discovery and precedence rules. If the active harness has no user-wide instruction mechanism, the correct outcome is to establish that from documentation and explain the limitation, without fabricating a path; define that profile's scoring before running it.

Grade file placement, preservation, and unintended permission expansion from the final filesystem diff. Grade the documentation lookup and whether it preceded the edit from the trace; a citation in the final answer alone is insufficient. Review focused clarification manually or with a fixed rubric. Reject real service access and edits outside the disposable workspace. Keep candidate-visible prompts separate from the private rubric when wiring them into a runner.

**Observed — repository inspection, 2026-10-10:** The current Promptfoo custom provider handles a narrow Home Assistant MCP loop and has no general filesystem agent runner. These cases are defined but have not been run or scored. A future runner should expose only the disposable files and documented lookup tools, return a trace and diff to Promptfoo, and avoid adapting the HA-specific provider into a general shell agent. Any harness with direct filesystem tools needs OS-level isolation so a benchmark cannot edit real user instructions.
