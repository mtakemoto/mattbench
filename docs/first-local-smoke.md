# First local FreeToken smoke run — 2026-10-10 PDT

**Reported:** The owner said FreeToken was serving a Qwen 3.6 variant on a localhost port.

**Observed — live preflight:** The local `/v1/models` endpoint returned HTTP 200 and one model ID, `Qwen3.6-35B-A3B-heretic-NVFP4-MTP-FTW`. The benchmark's ignored `.env` now holds the loopback base URL and that exact ID. The run path rejects non-loopback URLs, checks the model list before evaluation, clears hosted API key variables, and uses an OpenAI-compatible provider with `apiKeyRequired: false` and `useDefaultApiKey: false`. It has no OpenRouter provider or fallback. [FreeToken's quick start](https://github.com/FlashML-org/FreeToken/blob/main/docs/quickstart.md) documents the compatible API; [Promptfoo's OpenAI provider guide](https://www.promptfoo.dev/docs/providers/openai/#connection-settings) documents these connection settings.

**Observed — Promptfoo `0.124.1` run:** Evaluation `eval-cRq-2026-10-11T01:23:57` ran the same two pinned tasks and exact-answer assertion as the hosted smoke, one request per task, no cache, concurrency one. The local provider used `temperature: 0`, `max_tokens: 512`, and `showThinking: false`; no tools or system prompt were supplied.

| Task | Strict grade / output | Input / output tokens | Latency |
|---|---|---:|---:|
| `strawberry_r_count` | Pass / `3` | 29 / 332 | 44,855 ms |
| `car_wash_transport` | Fail / `WALK` | 41 / 253 | 5,069 ms |
| **Total** | **1/2** | **70 / 585** | **49,957 ms run duration** |

The [HTML report](../artifacts/promptfoo-local-smoke.html) and [JSON export](../artifacts/promptfoo-local-smoke.json) are ignored local artifacts. Promptfoo reported 655 total tokens and no dollar cost field. There was no hosted API charge; local power and hardware cost were not measured. The first request may include warm-up time, but that cause was not verified. One run of two simple prompts cannot establish broader Qwen or FreeToken performance.

**Unknown:** FreeToken runtime version, local checkpoint provenance beyond the served ID, hardware use during the run, and a separate response model field. The served model list had only the configured ID, but the Promptfoo export did not expose an independent response model value. No tool-call behavior was tested.

## Frozen inputs

- `tasks/smoke.json` SHA-256: `8691b80685ba4b61cf402d663e3227a643498a2254eb3ca32ec56e5c576ebe8b`
- `assertions/exact-answer.cjs` SHA-256: `4305c725a520e3998011b6e4de25b06ae2286cea9c6431f1e6bb3847ba190b4b`
- `promptfooconfig.cjs` SHA-256: `765e2d2fe4e136f01c45ddd45ed11bbc8c29df2d159e257c491630c158e6823a`
- `promptfooconfig.local.cjs` SHA-256: `6393ecf12a8aeaba3da5f51cb44f4af31f0e82ed4f81b824d1dc1fb40795586d`
- `scripts/local-settings.cjs` SHA-256: `74b170e1e1827bdc6c29b650df8afee6826b0296378ef9aa218378efca4ebf52`
- `scripts/preflight-local.cjs` SHA-256: `8ca6fc7f40b94be7c29aab3ccfca4d1b272bf8072cb8c405e4b87120e28bba75`
- `package-lock.json` SHA-256: `f65020e05efc48aa9de1aa680bce4ec3e649f342674218908798d5ad16ce87ec`
