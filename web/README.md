# mattbench console

This SvelteKit app runs locally against the repository's Inspect AI benchmark harness. It reads sanitized rows from the ignored `artifacts/inspect/summary.json` file. Raw Inspect logs and the worker log stay ignored on this machine.

From the repository root, install the pinned Python environment first:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-inspect.txt
.venv/bin/python scripts/inspect-report.py
```

Then install and run the web app:

```bash
cd web
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. For a standalone server, run `npm run build`, then `HOST=127.0.0.1 PORT=4173 node build` from `web/`.

## Sources and run limits

- **FreeToken:** Reads `MATTBENCH_LOCAL_BASE_URL` from the repository's ignored `.env`, lists `/v1/models`, and uses the exact selected model. If the endpoint is unavailable, the run stops.
- **OpenRouter:** Reads `OPENROUTER_API_KEY` from the same ignored `.env`. Its public model catalog powers search. Before running, enter the active workspace cap (up to the current $20 pilot ceiling) and explicitly confirm it. The cap must be configured at OpenRouter; this app does not dynamically stop a running API request based on spend. Base or careful makes two calls; compare both makes four. Model API retries are disabled.
- **Other endpoint:** Enter a literal private or loopback HTTP address ending in `/v1` (for example, another local port or a private network model server). The app discovers served model IDs. This profile uses OpenAI-compatible chat completions and a local placeholder API key; endpoints requiring their own authentication are future work.

The run button currently launches only the two pinned no-tool smoke tasks. The report also displays previous HA, coding, and Pi pilot activity when those logs are present. A two-question score is a workflow screen, not a model ranking. Costs appear only when Inspect reports them; local compute cost is not measured.

The app is for one owner on loopback. Do not expose it to a public network without adding authentication and a stronger endpoint access policy.

The app's `DESIGN.md` and `.impeccable/design.json` are relative symlinks to the repository's design system. This keeps one source of truth while allowing the design checker to discover it inside the Svelte package boundary.
