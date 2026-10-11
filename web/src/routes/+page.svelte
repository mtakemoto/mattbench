<script lang="ts">
  import { onMount } from 'svelte';
  import { ArrowUpRight, ChartNoAxesCombined, Clock3, Radio, Network, Search, ArrowRight, Info } from '@lucide/svelte';
  import type { PageProps } from './$types';
  import './console.css';

  type Source = 'freetoken' | 'openrouter' | 'compatible';
  type Model = { id: string; name: string; contextLength?: number };
  type Row = { task: string; run_id: string; sample_id: string; prompt_variant: string; model: string; concrete_response_model?: string; passed: boolean | null; latency_seconds?: number; usage?: Record<string, { total_tokens?: number; total_cost?: number | null }>; started_at?: string; inference?: { temperature?: number; max_tokens?: number; max_retries?: number; timeout?: number }; inspect_version?: string; task_version?: string; fixture?: string; log_file?: string };
  type Job = { status: 'running' | 'complete' | 'failed' | 'interrupted'; source: Source; model: string; error?: string };
  let { data }: PageProps = $props();
  let refreshedRows = $state.raw<Row[] | null>(null);
  let refreshedJob = $state.raw<Job | null | undefined>(undefined);
  let rows = $derived(refreshedRows ?? (data.rows as Row[]));
  let job = $derived(refreshedJob === undefined ? (data.job as Job | null) : refreshedJob);
  let source = $state<Source>('freetoken');
  let baseUrl = $state('http://127.0.0.1:11434/v1');
  let query = $state('');
  let catalog = $state.raw<Model[]>([]);
  let selectedModel = $state('');
  let variant = $state<'base' | 'careful' | 'both'>('both');
  let capUsd = $state(20);
  let capConfirmed = $state(false);
  let loading = $state(false);
  let catalogError = $state('');
  let runError = $state('');
  let filter = $state<'all' | 'local' | 'hosted'>('all');
  let selectedKey = $state('');
  let searchTimer: ReturnType<typeof setTimeout>;
  let catalogRequest = 0;
  const sourceNames: Record<Source, string> = { freetoken: 'FreeToken', openrouter: 'OpenRouter', compatible: 'Other endpoint' };
  let maxCalls = $derived(variant === 'both' ? 4 : 2);
  let canRun = $derived(Boolean(selectedModel) && !loading && job?.status !== 'running' && (source !== 'openrouter' || (data.sources.openrouter.configured && capConfirmed && capUsd > 0 && capUsd <= 20)));
  function name(model: string) { return model.replace(/^openai-api\/(freetoken|openrouter|compatible)\//, ''); }
  function short(model: string) { const text = name(model); return text.length > 31 ? `${text.slice(0, 29)}…` : text; }
  function route(model: string) { return model.startsWith('openai-api/openrouter/') ? 'OpenRouter' : model.startsWith('openai-api/compatible/') ? 'Other endpoint' : 'FreeToken'; }
  function tokens(row: Row) { return Object.values(row.usage || {}).reduce((total, use) => total + (use.total_tokens || 0), 0); }
  function cost(row: Row): number | null { const values = Object.values(row.usage || {}).map((use) => use.total_cost).filter((value): value is number => typeof value === 'number'); return values.length ? values.reduce((sum, value) => sum + value, 0) : null; }
  function fmt(value: number) { return new Intl.NumberFormat('en-US').format(value); }
  function secs(value?: number) { return value == null ? '—' : `${value.toFixed(value < 10 ? 1 : 0)}s`; }
  function taskName(id: string) { return ({ strawberry_r_count: 'Strawberry count', car_wash_transport: 'Car wash', clamp_fix: 'Clamp repair', north_room_coordinator_target: 'HA chained write', instruction_scope_ambiguous_reference: 'Instruction scope' } as Record<string, string>)[id] || id.replaceAll('_', ' '); }
  let matrix = $derived.by(() => {
    const groups = new Map<string, Row[]>();
    for (const row of rows.filter((r) => r.task === 'smoke' && !r.model.startsWith('mockllm/'))) {
      const key = `${row.model}|${row.prompt_variant}|${row.run_id}`;
      groups.set(key, [...(groups.get(key) || []), row]);
    }
    const latest = new Map<string, Row[]>();
    for (const group of groups.values()) {
      const key = `${group[0].model}|${group[0].prompt_variant}`;
      const previous = latest.get(key);
      if (!previous || (group[0].started_at || '') > (previous[0].started_at || '')) latest.set(key, group);
    }
    return [...latest.values()].map((group) => ({
      key: `${group[0].model}|${group[0].prompt_variant}`, model: group[0].model, prompt: group[0].prompt_variant,
      berry: group.find((r) => r.sample_id === 'strawberry_r_count'), wash: group.find((r) => r.sample_id === 'car_wash_transport'),
      pass: group.filter((r) => r.passed === true).length, scored: group.filter((r) => r.passed !== null).length,
      time: group.reduce((sum, r) => sum + (r.latency_seconds || 0), 0), tokens: group.reduce((sum, r) => sum + tokens(r), 0), cost: group.some((r) => cost(r) !== null) ? group.reduce((sum, r) => sum + (cost(r) || 0), 0) : null,
      sample: group[0]
    })).filter((g) => filter === 'all' || (filter === 'hosted' ? route(g.model) === 'OpenRouter' : route(g.model) !== 'OpenRouter'));
  });
  let selectedRun = $derived(matrix.find((entry) => entry.key === selectedKey));
  let recent = $derived([...rows].filter((r) => !r.model.startsWith('mockllm/')).sort((a, b) => (b.started_at || '').localeCompare(a.started_at || '')).slice(0, 6));

  async function loadModels() {
    const requestId = ++catalogRequest;
    loading = true; catalogError = '';
    try {
      const params = new URLSearchParams({ source, q: query });
      if (source === 'compatible') params.set('baseUrl', baseUrl);
      const response = await fetch(`/api/models?${params}`);
      const body = await response.json();
      if (requestId !== catalogRequest) return;
      if (!response.ok) throw new Error(body.error || 'Catalog unavailable.');
      catalog = body.models;
      if (!catalog.some((m) => m.id === selectedModel)) selectedModel = source === 'freetoken' ? catalog.find((m) => m.id === data.sources.freetoken.defaultModel)?.id || catalog[0]?.id || '' : '';
    } catch (cause) { if (requestId === catalogRequest) { catalog = []; selectedModel = ''; catalogError = cause instanceof Error ? cause.message : 'Catalog unavailable.'; } }
    finally { if (requestId === catalogRequest) loading = false; }
  }
  function chooseSource(next: Source) { ++catalogRequest; source = next; query = ''; selectedModel = ''; catalog = []; catalogError = ''; runError = ''; loading = false; if (next !== 'compatible') void loadModels(); }
  function search() { clearTimeout(searchTimer); searchTimer = setTimeout(() => void loadModels(), 260); }
  async function refresh() { const response = await fetch('/api/overview', { cache: 'no-store' }); if (response.ok) { const body = await response.json(); refreshedRows = body.rows; refreshedJob = body.job; } }
  async function run() {
    runError = '';
    try {
      const response = await fetch('/api/runs', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ source, model: selectedModel, variant, baseUrl: source === 'compatible' ? baseUrl : undefined, maxCalls, capUsd: source === 'openrouter' ? capUsd : undefined, capConfirmed: source === 'openrouter' ? capConfirmed : undefined }) });
      const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Could not start run.'); refreshedJob = body.job;
    } catch (cause) { runError = cause instanceof Error ? cause.message : 'Could not start run.'; }
  }
  onMount(() => { void loadModels(); const timer = setInterval(() => { if (job?.status === 'running') void refresh(); }, 3500); return () => { clearInterval(timer); clearTimeout(searchTimer); }; });
</script>

<div class="shell">
  <aside class="rail" aria-label="Primary navigation">
    <a class="brand" href="#top" aria-label="mattbench home"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>matt<span>bench</span></a>
    <nav><a class="active" href="#run"><ArrowUpRight size={19} aria-hidden="true"/>Run a benchmark</a><a href="#report"><ChartNoAxesCombined size={19} aria-hidden="true"/>Results</a><a href="#activity"><Clock3 size={19} aria-hidden="true"/>Activity</a></nav>
    <div class="rail-foot"><i></i> LOCAL CONSOLE <span>v0.1</span></div>
  </aside>
  <main id="top">
    <header class="topbar"><span>BENCH LAB <i>/</i> CONTROL ROOM</span><span class="engine"><i></i> INSPECT AI ENGINE <em></em> PILOT BUILD</span></header>
    <section class="masthead"><div><h1>Make your models<br /><em>prove it.</em></h1><p>Run the same task with a different model or prompt. See exactly what passed, how long it took, and what it used.</p></div><div class="dial" aria-hidden="true"><span>MB</span><small>MEASURE<br />THEN MOVE</small></div></section>
    <div class="workspace">
      <section class="run-panel" id="run" aria-labelledby="run-title">
        <div class="section-head"><div><h2 id="run-title">Set up a run<span>.</span></h2><p>One pinned suite. One selected model. A clean comparison.</p></div><b>2 TASKS</b></div>
        <div class="field"><div class="field-head"><strong>Model source</strong><span>Choose where requests go</span></div><div class="source-grid" role="group" aria-label="Model source">
          {#each ['freetoken', 'openrouter', 'compatible'] as option (option)}<button type="button" class:selected={source === option} aria-pressed={source === option} onclick={() => chooseSource(option as Source)}><span class="symbol" aria-hidden="true">{#if option === 'freetoken'}<Radio size={22}/>{:else if option === 'openrouter'}<ArrowUpRight size={22}/>{:else}<Network size={22}/>{/if}</span><strong>{sourceNames[option as Source]}</strong><small>{option === 'freetoken' ? 'This machine' : option === 'openrouter' ? 'Hosted' : 'Private / LAN'}</small></button>{/each}
        </div></div>
        {#if source === 'compatible'}<div class="field"><div class="field-head"><label for="endpoint">OpenAI-compatible endpoint</label><span>Private HTTP /v1</span></div><div class="input-action"><input id="endpoint" type="url" bind:value={baseUrl} spellcheck="false" /><button type="button" onclick={loadModels}>Connect</button></div></div>{/if}
        <div class="field"><div class="field-head"><label for="model-search">Model</label><span>{loading ? 'Checking catalog…' : `${catalog.length} shown`}</span></div><div class="search"><Search size={17} aria-hidden="true"/><input id="model-search" placeholder={source === 'openrouter' ? 'Search OpenRouter models' : 'Filter served models'} bind:value={query} oninput={search} autocomplete="off" /></div>
          {#if catalogError}<div class="message error" role="alert">{catalogError} <button type="button" onclick={loadModels}>Retry</button></div>{:else if loading}<div class="catalog-empty">Checking available models…</div>{:else if !catalog.length}<div class="catalog-empty">{source === 'compatible' ? 'Enter an endpoint and connect to list its models.' : 'No matching models. Try another search.'}</div>{:else}<div class="model-list" role="radiogroup" aria-label="Available models">{#each catalog as option (option.id)}<label class:chosen={selectedModel === option.id}><input type="radio" name="model" value={option.id} bind:group={selectedModel} /><i></i><span><strong>{option.name}</strong><small>{option.id}</small></span>{#if option.contextLength}<em>{Math.round(option.contextLength / 1000)}K CTX</em>{/if}</label>{/each}</div>{/if}
        </div>
        <div class="field"><div class="field-head"><strong>Prompt treatment</strong><span>Same pinned questions</span></div><div class="variant-grid" role="group" aria-label="Prompt treatment">{#each [{ id: 'base', label: 'Base', sub: 'Original prompt' }, { id: 'careful', label: 'Careful', sub: 'Guided system note' }, { id: 'both', label: 'Compare both', sub: 'Side by side' }] as choice (choice.id)}<button type="button" class:selected={variant === choice.id} aria-pressed={variant === choice.id} onclick={() => variant = choice.id as typeof variant}><strong>{choice.label}</strong><small>{choice.sub}</small></button>{/each}</div></div>
        {#if source === 'openrouter'}<div class="paid"><h3><span>$</span> Paid run guard</h3><p>OpenRouter's workspace cap is the spend stop. This run makes exactly {maxCalls} requests with retries disabled.</p><label for="cap">Active workspace cap (USD)</label><input id="cap" type="number" min="0.01" max="20" step="0.01" bind:value={capUsd} /><label class="check"><input type="checkbox" bind:checked={capConfirmed} /> I confirm this cap is active in OpenRouter.</label>{#if !data.sources.openrouter.configured}<p class="warning">Add OPENROUTER_API_KEY to the ignored .env to enable hosted runs.</p>{/if}</div>{/if}
        <div class="run-actions"><div class="call-count"><strong>{maxCalls}</strong><small>MAX MODEL<br />CALLS</small></div><button class="run-button" type="button" disabled={!canRun} onclick={run}><span>{job?.status === 'running' ? 'RUN IN PROGRESS' : 'RUN BENCHMARK'}</span><ArrowRight size={19} aria-hidden="true"/></button></div>
        {#if runError}<div class="message error" role="alert">{runError}</div>{/if}
        {#if job}<div class:working={job.status === 'running'} class="job" role="status"><i></i><span><strong>{job.status === 'running' ? 'Benchmark is running' : job.status === 'complete' ? 'Run complete' : 'Run stopped'}</strong><small>{job.status === 'running' ? `${sourceNames[job.source]} · ${short(job.model)} · results appear when complete` : job.error || `${sourceNames[job.source]} · ${short(job.model)}`}</small></span>{#if job.status !== 'running'}<button type="button" onclick={refresh}>Refresh</button>{/if}</div>{/if}
      </section>
      <section class="report-panel" id="report" aria-labelledby="report-title">
        <div class="section-head"><div><h2 id="report-title">The scorecard<span>.</span></h2><p>Actual Inspect results from pinned smoke questions.</p></div><b>LIVE DATA</b></div>
        <div class="note"><Info size={17} aria-hidden="true"/> These pilot questions screen the workflow. Two tasks cannot establish broad model superiority.</div>
        <div class="report-toolbar"><strong>MODEL × PROMPT</strong><div role="group" aria-label="Filter results"><button class:selected={filter === 'all'} onclick={() => filter = 'all'}>All</button><button class:selected={filter === 'local'} onclick={() => filter = 'local'}>Local</button><button class:selected={filter === 'hosted'} onclick={() => filter = 'hosted'}>Hosted</button></div></div>
        {#if matrix.length}
          <div class="matrix-wrap"><table><thead><tr><th scope="col">Model / prompt</th><th scope="col">Strawberry</th><th scope="col">Car wash</th><th scope="col">Score</th><th scope="col">Time</th><th scope="col">Tokens</th><th scope="col">Cost</th></tr></thead><tbody>
            {#each matrix as entry (entry.key)}
              <tr><th scope="row"><strong>{short(entry.model)}</strong><small>{route(entry.model)} · {entry.prompt} prompt</small><button class="detail-link" type="button" aria-expanded={selectedKey === entry.key} onclick={() => selectedKey = selectedKey === entry.key ? '' : entry.key}>Run details</button></th>
                <td><span class:pass={entry.berry?.passed === true} class:miss={entry.berry?.passed === false} class="result">{entry.berry ? entry.berry.passed === true ? 'PASS' : entry.berry.passed === false ? 'MISS' : 'UNSCORED' : 'NOT RUN'}</span></td>
                <td><span class:pass={entry.wash?.passed === true} class:miss={entry.wash?.passed === false} class="result">{entry.wash ? entry.wash.passed === true ? 'PASS' : entry.wash.passed === false ? 'MISS' : 'UNSCORED' : 'NOT RUN'}</span></td>
                <td><div class="score"><strong>{entry.scored ? `${entry.pass}/${entry.scored}` : '—'}</strong><span><i style:width={`${entry.pass * 50}%`}></i></span></div></td><td class="numeric">{secs(entry.time)}</td><td class="numeric">{fmt(entry.tokens)}</td><td class="numeric">{entry.cost === null ? '—' : `$${entry.cost.toFixed(6)}`}</td>
              </tr>
            {/each}
          </tbody></table></div>
        {:else}<div class="empty"><div aria-hidden="true">×</div><strong>No scored runs in this view yet.</strong><p>Pick a model, run the two-question suite, and its task results will land here.</p></div>{/if}
        {#if selectedRun}
          <div class="run-detail" aria-label="Selected run details"><div class="detail-head"><h3>Run details</h3><button type="button" onclick={() => selectedKey = ''}>Close</button></div><dl>
            <div><dt>Exact model ID</dt><dd>{name(selectedRun.model)}</dd></div><div><dt>Source</dt><dd>{route(selectedRun.model)}</dd></div>
            <div><dt>Prompt</dt><dd>{selectedRun.prompt}</dd></div><div><dt>Run ID</dt><dd>{selectedRun.sample.run_id}</dd></div>
            <div><dt>Response model</dt><dd>{selectedRun.sample.concrete_response_model || 'Not reported'}</dd></div><div><dt>Started</dt><dd>{selectedRun.sample.started_at || 'Not reported'}</dd></div>
            <div><dt>Inference</dt><dd>Temperature {selectedRun.sample.inference?.temperature ?? '—'} · max {selectedRun.sample.inference?.max_tokens ?? '—'} tokens · {selectedRun.sample.inference?.max_retries ?? '—'} retries · {selectedRun.sample.inference?.timeout ?? '—'}s timeout</dd></div>
            <div><dt>Fixture / version</dt><dd>{selectedRun.sample.fixture || '—'} · task v{selectedRun.sample.task_version || '—'} · Inspect {selectedRun.sample.inspect_version || '—'}</dd></div>
            <div><dt>Inspect log</dt><dd>{selectedRun.sample.log_file || 'Not reported'}</dd></div>
          </dl></div>
        {/if}
        <div class="activity" id="activity"><div class="activity-head"><h3>Recent activity</h3><span>ALL TASK FAMILIES</span></div>{#if recent.length}{#each recent as row (`${row.run_id}-${row.sample_id}-${row.prompt_variant}`)}<div class="activity-row"><i class:good={row.passed === true} class:bad={row.passed === false}></i><div><strong>{taskName(row.sample_id)}</strong><small>{short(row.model)} · {row.prompt_variant} prompt</small></div><aside><strong>{row.passed === true ? 'PASS' : row.passed === false ? 'MISS' : '—'}</strong><small>{secs(row.latency_seconds)} · {fmt(tokens(row))} tok</small></aside></div>{/each}{:else}<p class="activity-empty">Run a benchmark to build an activity trail.</p>{/if}</div>
      </section>
    </div>
    <footer><span>mattbench / personal evaluation lab</span><span>Fixtures and scores stay pinned. Raw traces stay local.</span></footer>
  </main>
</div>
