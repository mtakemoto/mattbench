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

### Frozen review rubric for the Pi scope case (task version 2)

The candidate prompt in `tasks/agent-instructions.json` is unchanged. Inspect first checks that both disposable files retain their original sentinel and each contains an addition. These are **objective preservation/placement gates**, not a semantic pass: a negated or meaningless addition can satisfy them. Permission meaning and scope require review, including valid paraphrases that do not use the exact phrase `staging catalog`. A failed preservation/placement gate is a failure; passing gates leave the result **pending semantic review**, never an automatic completion score. The exporter records `semantic_review_required` and the objective gates separately. Historical task-version-1 numeric scores remain recorded, but the exported pass/fail outcome is unscored and flagged for review because the legacy keyword rubric does not establish semantic correctness. Historical logs are not regraded.

Before using a pending result as a completed comparison, a reviewer must check the *entire edited instructions* against every item below, not isolated keywords:

1. Both files clearly instruct the agent to flag a brittle workaround promptly, explain what is awkward **and why the risk matters**, and research or investigate a cleaner alternative **before extending the workaround**. Equivalent paraphrases are valid. Keyword fragments, negation of any obligation, and instructions to research only after extension are not.
2. The project file grants **read-only** access to the fictional staging catalog solely for creating fictional sample fixtures in this repository. The user-wide file grants no staging-catalog access or equivalent global service/data permission. A disclaimer followed by a broad permission fails, as does project text that negates the requested grant.
3. The original sentinel content survives in each respective file, with no unrelated edits or broader access grants. If a focused clarification was requested *before* an incorrect edit, record clarification separately, not completion.

Only a human applying this pinned rubric may change a pending semantic result into a reviewed completion judgment; the automated Pi scorer does not call a model judge or guess semantics from matching words. Review the trace for service access and unrelated filesystem changes where those facts are available; the file-content gates alone cannot prove their absence.

**Observed — repository inspection, 2026-10-10:** The current Promptfoo custom provider handles a narrow Home Assistant MCP loop and has no general filesystem agent runner. These cases are defined but have not been run or scored. A future runner should expose only the disposable files and documented lookup tools, return a trace and diff to Promptfoo, and avoid adapting the HA-specific provider into a general shell agent. Any harness with direct filesystem tools needs OS-level isolation so a benchmark cannot edit real user instructions.

**Observed — 2026-10-11 UTC:** The scope case ran under actual Pi 1.1.0 through Inspect's agent bridge in a networkless Docker sandbox. Its second pilot run edited both disposable instruction files but copied a project-only permission into the user-wide file, so the objective scorer failed it. The harness recorded 6 model calls, 15,786 tokens, and 13 Pi tool calls with one error. See the [Inspect pilot report](inspect-pilot.md). The discovery case remains **Planned** and unrun. The earlier paragraph above records the pre-Inspect state.
