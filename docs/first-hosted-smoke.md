# First hosted smoke run — 2026-10-10 PDT

**Observed:** One Promptfoo `0.124.1` run (`eval-NJ9-2026-10-11T01:19:01`) made two OpenRouter requests through configured model ID `z-ai/glm-5.3-flash`. The prompt was each task's text as written, with no system prompt or tools. Settings: `temperature: 0`, `max_tokens: 512`, no cache, one repeat, concurrency one. The run used the owner's **Reported** $20/week workspace cap and stopped after the two pinned cases. It made no Home Assistant request.

| Task | Promptfoo original grade | Final answer in response | Input / output tokens | Reasoning tokens | Latency | Reported account charge |
|---|---|---|---:|---:|---:|---:|
| `strawberry_r_count` | Fail | `3` | 31 / 95 | 49 | 730 ms | $0.00005215 |
| `car_wash_transport` | Fail | `DRIVE` | 42 / 148 | 145 | 3262 ms | $0.00007694 |
| **Total** | **0/2 strict grades** | **2/2 correct final answers** | **73 / 243** | **194** | **4012 ms run duration** | **$0.00012909** |

**Observed:** [The exact-answer grader](../assertions/exact-answer.cjs) requires the complete scored output to equal the expected short answer after trimming and case folding. Promptfoo's OpenRouter adapter added `Thinking: ...` before each final answer because its `showThinking` option defaults to true. Both full outputs therefore failed the grader. The final answers above were inspected after the run; they are a **post hoc observation**, not a replacement score for the frozen evaluation. The [original HTML report](../artifacts/promptfoo-openrouter-glm-5.3-flash.html) and [JSON export](../artifacts/promptfoo-openrouter-glm-5.3-flash.json) remain in ignored local artifacts.

**Observed — local code inspection:** Promptfoo's Chat provider builds scored output from the model's separate reasoning and content fields when `showThinking` is true. The [OpenRouter provider documentation](https://www.promptfoo.dev/docs/providers/openrouter/#thinkingreasoning-models) documents `showThinking: false` for hiding reasoning from output. The hosted config now sets that option, and `promptfoo validate config` passes.

**Unknown:** The export records the configured OpenRouter model ID and `isByok: false`, but does not expose a separate concrete response model or hosting provider. No claim about the route beyond the configured ID is possible from this artifact. The charge is Promptfoo's reported OpenRouter `usage.cost`, not an independently reconciled invoice. Two riddles cannot establish Home Assistant or coding performance.

## Frozen run inputs

- `tasks/smoke.json` SHA-256: `8691b80685ba4b61cf402d663e3227a643498a2254eb3ca32ec56e5c576ebe8b`
- `assertions/exact-answer.cjs` SHA-256: `4305c725a520e3998011b6e4de25b06ae2286cea9c6431f1e6bb3847ba190b4b`
- `promptfooconfig.cjs` SHA-256: `765e2d2fe4e136f01c45ddd45ed11bbc8c29df2d159e257c491630c158e6823a`
- Original `promptfooconfig.openrouter.cjs` SHA-256: `ab4b7bf877f94a2d8eb5a0059a92eca14bcfb1ffed333318c0e50edc95cd7646`
- `package-lock.json` SHA-256: `f65020e05efc48aa9de1aa680bce4ec3e649f342674218908798d5ad16ce87ec`

The corrected hosted configuration differs from the first run input only by `showThinking: false`; its SHA-256 is `d9203f79024f971e389c1d8116d4fa230107d0e9e754ebd30addbadcc7992b96`.

## Corrected verification run

**Observed — 2026-10-10 PDT:** One additional run (`eval-8ui-2026-10-11T01:20:45`) used the same fixtures, assertion, model ID, inference settings, and two-request stop condition, with `showThinking: false`. Both strict assertions passed. Promptfoo scored the model's final content while still counting reasoning tokens. The [HTML report](../artifacts/promptfoo-openrouter-glm-5.3-flash-v2.html) and [JSON export](../artifacts/promptfoo-openrouter-glm-5.3-flash-v2.json) are separate ignored local artifacts.

| Task | Strict grade / output | Input / output tokens | Reasoning tokens | Latency | Reported account charge |
|---|---|---:|---:|---:|---:|
| `strawberry_r_count` | Pass / `3` | 31 / 60 | 34 | 1279 ms | $0.00003465 |
| `car_wash_transport` | Pass / `DRIVE` | 42 / 91 | 88 | 1982 ms | $0.00004844 |
| **Total** | **2/2** | **73 / 151** | **122** | **3281 ms run duration** | **$0.00008309** |

Across both hosted runs, Promptfoo recorded four requests and $0.00021218 in OpenRouter account charges. The first 0/2 score was a harness display issue; the corrected run is the usable strict smoke result. This tiny suite only confirms that the two simple no-tool answers and reporting path work. A concrete response model or hosting provider still was not exposed in the export.
