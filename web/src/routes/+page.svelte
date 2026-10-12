<script lang="ts">
  import { onMount } from 'svelte';
  import { ArrowUpRight, ChartNoAxesCombined, Clock3, Radio, Network, Search, ArrowRight, Info } from '@lucide/svelte';
  import type { PageProps } from './$types';
  import './console.css';

  type Source = 'freetoken' | 'openrouter' | 'compatible';
  type Model = { id: string; name: string; contextLength?: number };
  type RunTiming = { setup_seconds?: number; evaluation_seconds?: number; teardown_seconds?: number; total_wall_seconds?: number };
  type Row = { task: string; run_id: string; launcher_run_id?: string; sample_id: string; prompt_variant: string; model: string; concrete_response_model?: string; routed_models?: string[]; providers?: string[]; passed: boolean | null; score_explanation?: string; score_metadata?: Record<string, { state_correct?: boolean; trace_valid?: boolean }>; latency_seconds?: number; model_calls?: number; usage?: Record<string, { total_tokens?: number; total_cost?: number | null }>; started_at?: string; inference?: { temperature?: number; max_tokens?: number; max_retries?: number; timeout?: number }; inspect_version?: string; task_version?: string; fixture?: string; log_file?: string; run_timing?: RunTiming };
  type BenchmarkCase = { id: string; name: string; category: string; suite: 'smoke' | 'ha'; fixture: string; maxModelCalls?: number };
  type CaseTiming = { case_id: string; status: string; setup_seconds: number; evaluation_seconds: number; teardown_seconds: number; total_wall_seconds: number };
  type Job = { id: string; status: 'running' | 'complete' | 'failed' | 'interrupted'; phase?: string; source: Source; model: string; caseId?: string; currentCaseId?: string; completedCases?: { caseId: string; status: string; passed?: boolean; modelCalls?: number; message?: string }[]; completedCount?: number; totalCases?: number; message?: string; error?: string };
  let { data }: PageProps = $props();
  let refreshedRows = $state.raw<Row[] | null>(null);
  let refreshedJob = $state.raw<Job | null | undefined>(undefined);
  let refreshedTimings = $state.raw<CaseTiming[] | null>(null);
  let rows = $derived(refreshedRows ?? (data.rows as Row[]));
  let job = $derived(refreshedJob === undefined ? (data.job as Job | null) : refreshedJob);
  let timings = $derived(refreshedTimings ?? (data.runTimings as CaseTiming[]));
  let source = $state<Source>('freetoken');
  let baseUrl = $state('http://127.0.0.1:11434/v1');
  let query = $state('');
  let catalog = $state.raw<Model[]>([]);
  let selectedModel = $state('');
  let variant = $state<'base' | 'careful' | 'both'>('both');
  let caseId = $state('all');
  let capUsd = $state(20);
  let capConfirmed = $state(false);
  let loading = $state(false);
  let catalogError = $state('');
  let runError = $state('');
  let filter = $state<'all' | 'local' | 'hosted'>('all');
  let selectedKey = $state('');
  let selectedReportRunKey = $state('');
  let selectedActivityRunKey = $state('');
  let searchTimer: ReturnType<typeof setTimeout>;
  let catalogRequest = 0;
  const sourceNames: Record<Source, string> = { freetoken: 'FreeToken', openrouter: 'OpenRouter', compatible: 'Other endpoint' };
  let availableCases = $derived(data.cases as BenchmarkCase[]);
  let caseGroups = $derived.by(() => {
    const groups: Record<string, BenchmarkCase[]> = Object.create(null) as Record<string, BenchmarkCase[]>;
    for (const entry of availableCases.filter((item) => item.suite === 'ha')) {
      groups[entry.category] = [...(groups[entry.category] || []), entry];
    }
    return Object.entries(groups).map(([id, entries]) => ({ id, label: id === 'smart_home' ? 'Smart home' : id.replaceAll('_', ' '), entries }));
  });
  let visibleCases = $derived(caseId === 'all' ? availableCases : availableCases.filter((entry) => entry.suite === (caseId === 'smoke' ? 'smoke' : 'ha') && (caseId === 'smoke' || entry.id === caseId)));
  let caseTiming = $derived(timings.find((entry) => entry.case_id === caseId));
  let totalCallCap = $derived(availableCases.filter((entry) => entry.suite === 'ha').reduce((sum, entry) => sum + (entry.maxModelCalls || 0), 2));
  let maxCalls = $derived(caseId === 'all' ? totalCallCap : caseId === 'smoke' ? variant === 'both' ? 4 : 2 : availableCases.find((entry) => entry.id === caseId)?.maxModelCalls || 0);
  let canRun = $derived(Boolean(selectedModel) && maxCalls > 0 && !loading && job?.status !== 'running' && (source !== 'openrouter' || (data.sources.openrouter.configured && capConfirmed && capUsd > 0 && capUsd <= 20)));
  function name(model: string) { return model.replace(/^openai-api\/(freetoken|openrouter|compatible)\//, ''); }
  function short(model: string) { const text = name(model); return text.length > 31 ? `${text.slice(0, 29)}…` : text; }
  function route(model: string) { return model.startsWith('openai-api/openrouter/') ? 'OpenRouter' : model.startsWith('openai-api/compatible/') ? 'Other endpoint' : 'FreeToken'; }
  function tokens(row: Row) { return Object.values(row.usage || {}).reduce((total, use) => total + (use.total_tokens || 0), 0); }
  function cost(row: Row): number | null { const values = Object.values(row.usage || {}).map((use) => use.total_cost).filter((value): value is number => typeof value === 'number'); return values.length ? values.reduce((sum, value) => sum + value, 0) : null; }
  function fmt(value: number) { return new Intl.NumberFormat('en-US').format(value); }
  function secs(value?: number) { return value == null ? '—' : `${value.toFixed(value < 10 ? 1 : 0)}s`; }
  function taskName(id: string) { return availableCases.find((entry) => entry.id === id)?.name || id.replaceAll('_', ' '); }
  function runKey(row: Row) { return JSON.stringify([row.launcher_run_id || row.run_id, row.model]); }
  function runTime(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Time not reported' : new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short'
    }).format(date);
  }
  let runs = $derived.by(() => {
    const groups: Record<string, Row[]> = Object.create(null) as Record<string, Row[]>;
    for (const row of rows.filter((entry) => !entry.model.startsWith('mockllm/'))) {
      const key = runKey(row);
      groups[key] = [...(groups[key] || []), row];
    }
    return Object.entries(groups).map(([key, group]) => {
      const ordered = [...group].sort((a, b) => (a.started_at || '').localeCompare(b.started_at || ''));
      return {
        key, rows: ordered, model: ordered[0].model, runId: ordered[0].launcher_run_id || ordered[0].run_id,
        startedAt: ordered[0].started_at || '', pass: ordered.filter((row) => row.passed === true).length,
        scored: ordered.filter((row) => row.passed !== null).length,
        unscored: ordered.filter((row) => row.passed === null).length,
        prompts: [...new Set(ordered.map((row) => row.prompt_variant))].join(' + ')
      };
    }).sort((a, b) => b.startedAt.localeCompare(a.startedAt));
  });
  function runScore(run: (typeof runs)[number]) { return run.scored ? `${run.pass} of ${run.scored} passed` : 'No scored tasks'; }
  function runLabel(run: (typeof runs)[number]) { return `${runTime(run.startedAt)} · ${name(run.model)} · ${runScore(run)}`; }
  let reportRuns = $derived(runs.filter((run) => run.rows.some((row) => availableCases.some((entry) => entry.id === row.sample_id)) && (filter === 'all' || (filter === 'hosted' ? route(run.model) === 'OpenRouter' : route(run.model) !== 'OpenRouter'))));
  let activityRuns = $derived(runs);
  let selectedReportRun = $derived(reportRuns.find((run) => run.key === selectedReportRunKey) || reportRuns[0]);
  let selectedActivityRun = $derived(activityRuns.find((run) => run.key === selectedActivityRunKey) || activityRuns[0]);
  let matrix = $derived.by(() => {
    const groups: Record<string, Row[]> = Object.create(null) as Record<string, Row[]>;
    for (const row of (selectedReportRun?.rows || []).filter((entry) => availableCases.some((benchmark) => benchmark.id === entry.sample_id))) {
      const key = row.prompt_variant;
      groups[key] = [...(groups[key] || []), row];
    }
    return Object.values(groups).map((group) => {
      const runId = group[0].launcher_run_id || group[0].run_id;
      return {
      key: `${group[0].model}|${group[0].prompt_variant}|${runId}`, runId, model: group[0].model, prompt: group[0].prompt_variant,
      cases: Object.fromEntries(group.map((row) => [row.sample_id, row])) as Record<string, Row>,
      pass: group.filter((r) => r.passed === true).length, scored: group.filter((r) => r.passed !== null).length,
      time: group.reduce((sum, r) => sum + (r.latency_seconds || 0), 0), setup: group.reduce((sum, r) => sum + (r.run_timing?.setup_seconds || 0), 0), cleanup: group.reduce((sum, r) => sum + (r.run_timing?.teardown_seconds || 0), 0), calls: group.every((r) => r.model_calls !== undefined) ? group.reduce((sum, r) => sum + (r.model_calls || 0), 0) : null, tokens: group.reduce((sum, r) => sum + tokens(r), 0), cost: group.every((r) => cost(r) !== null) ? group.reduce((sum, r) => sum + (cost(r) || 0), 0) : null, providers: [...new Set(group.flatMap((r) => r.providers || []))], routedModels: [...new Set(group.flatMap((r) => r.routed_models || []))],
      sample: group[0]
      };
    }).sort((a, b) => a.prompt.localeCompare(b.prompt));
  });
  let selectedRun = $derived(matrix.find((entry) => entry.key === selectedKey));
  let activeView = $state<'run' | 'results' | 'activity'>('run');
  let jobProgress = $derived(job?.totalCases ? Math.round(((job.completedCount || 0) / job.totalCases) * 100) : 0);
  let jobPhase = $derived(job?.phase?.replaceAll('_', ' ') || (job?.status === 'running' ? 'running' : job?.status || ''));
  let jobResults = $derived(rows.filter((row) => row.launcher_run_id === job?.id && availableCases.some((entry) => entry.id === row.sample_id)));
  let jobPassed = $derived(jobResults.filter((row) => row.passed === true).length);

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
    } catch (cause) { if (requestId === catalogRequest) { catalog = []; selectedModel = ''; const reason = cause instanceof Error ? cause.message : 'Catalog unavailable.'; catalogError = reason === 'fetch failed' ? source === 'freetoken' ? 'FreeToken is unavailable. Start it and retry.' : source === 'compatible' ? 'Could not reach this endpoint. Check its address and retry.' : 'Could not reach OpenRouter. Retry in a moment.' : reason; } }
    finally { if (requestId === catalogRequest) loading = false; }
  }
  function chooseSource(next: Source) { ++catalogRequest; source = next; query = ''; selectedModel = ''; catalog = []; catalogError = ''; runError = ''; loading = false; if (next !== 'compatible') void loadModels(); }
  function search() { clearTimeout(searchTimer); searchTimer = setTimeout(() => void loadModels(), 260); }
  function syncView() { const view = location.hash.slice(1); activeView = view === 'report' ? 'results' : view === 'activity' ? 'activity' : 'run'; }
  async function refresh() { const response = await fetch('/api/overview', { cache: 'no-store' }); if (response.ok) { const body = await response.json(); refreshedRows = body.rows; refreshedJob = body.job; refreshedTimings = body.runTimings; } }
  async function run() {
    runError = '';
    try {
      const response = await fetch('/api/runs', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ source, model: selectedModel, variant: caseId === 'smoke' ? variant : 'base', caseId, baseUrl: source === 'compatible' ? baseUrl : undefined, maxCalls, capUsd: source === 'openrouter' ? capUsd : undefined, capConfirmed: source === 'openrouter' ? capConfirmed : undefined }) });
      const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Could not start run.'); refreshedJob = body.job;
    } catch (cause) { runError = cause instanceof Error ? cause.message : 'Could not start run.'; }
  }
  onMount(() => { syncView(); window.addEventListener('hashchange', syncView); void loadModels(); const timer = setInterval(() => { void refresh(); }, 1800); return () => { window.removeEventListener('hashchange', syncView); clearInterval(timer); clearTimeout(searchTimer); }; });
</script>

<div class="shell">
  <aside class="rail" aria-label="Primary navigation">
    <a class="brand" href="#top" aria-label="mattbench home"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>matt<span>bench</span></a>
    <nav><a class:active={activeView === 'run'} href="#run" aria-current={activeView === 'run' ? 'page' : undefined}><ArrowUpRight size={19} aria-hidden="true"/>Run a benchmark</a><a class:active={activeView === 'results'} href="#report" aria-current={activeView === 'results' ? 'page' : undefined}><ChartNoAxesCombined size={19} aria-hidden="true"/>Results</a><a class:active={activeView === 'activity'} href="#activity" aria-current={activeView === 'activity' ? 'page' : undefined}><Clock3 size={19} aria-hidden="true"/>Activity</a></nav>
    <div class="rail-foot"><i></i> LOCAL CONSOLE</div>
  </aside>
  <main id="top">
    <header class="console-header"><h1>Benchmark console<span>.</span></h1><div class="console-facts"><span><strong>{availableCases.length}</strong> pinned cases</span><span><strong>{runs.length}</strong> recorded runs</span><span>Inspect AI</span></div></header>
    {#if job?.status === 'running'}
      <div class="run-live" role="status" aria-live="polite">
        <span class="run-live-spinner" aria-hidden="true"></span>
        <div class="run-live-copy"><strong>{job.currentCaseId ? taskName(job.currentCaseId) : 'Preparing run'}</strong><span>{job.message || `Run ${jobPhase}`} · {job.completedCount || 0} of {job.totalCases || 1} cases finished</span></div>
        <strong class="run-live-fraction">{job.completedCount || 0}/{job.totalCases || 1}</strong>
        <span class="run-live-track" role="progressbar" aria-label="Completed benchmark cases" aria-valuemin="0" aria-valuemax={job.totalCases || 1} aria-valuenow={job.completedCount || 0}><i style:transform={`scaleX(${jobProgress / 100})`}></i></span>
        {#if job.completedCases?.length}<div class="run-live-cases">{#each job.completedCases as done (done.caseId)}<span>{taskName(done.caseId)}: {done.status === 'failed' ? 'ERROR' : done.passed === true ? 'PASS' : done.passed === false ? 'FAIL' : 'DONE'}{done.modelCalls !== undefined ? ` · ${done.modelCalls} calls` : ''}</span>{/each}</div>{/if}
      </div>
    {/if}
      <div class:single={activeView !== 'run'} class="workspace">
      <section class="run-panel" class:view-hidden={activeView !== 'run'} id="run" aria-labelledby="run-title">
        <div class="section-head"><div><h2 id="run-title">Set up a run<span>.</span></h2></div><b>{visibleCases.length} {visibleCases.length === 1 ? 'TASK' : 'TASKS'}</b></div>
        <div class="field case-field"><div class="field-head"><strong>Choose a benchmark</strong><span>Pinned cases · {availableCases.length} total</span></div><div class="case-options" role="group" aria-label="Benchmark selection">
          <button class="case-option everything" class:selected={caseId === 'all'} type="button" aria-pressed={caseId === 'all'} onclick={() => caseId = 'all'}><span><strong>Run everything</strong><small>Smoke questions and every smart home case</small></span><b>{availableCases.length} TASKS</b></button>
          <button class="case-option" class:selected={caseId === 'smoke'} type="button" aria-pressed={caseId === 'smoke'} onclick={() => caseId = 'smoke'}><span><strong>Smoke questions</strong><small>{availableCases.filter((entry) => entry.suite === 'smoke').length} quick reasoning checks</small></span><b>SMOKE</b></button>
          {#each caseGroups as group (group.id)}<div class="case-category"><strong>{group.label}</strong><span>{group.entries.length} {group.entries.length === 1 ? 'case' : 'cases'}</span></div>{#each group.entries as entry (entry.id)}<button class="case-option" class:selected={caseId === entry.id} type="button" aria-pressed={caseId === entry.id} onclick={() => caseId = entry.id}><span><strong>{entry.name}</strong><small>Real ha-mcp · fresh synthetic home</small></span><b>{group.label.toUpperCase()}</b></button>{/each}{/each}
        </div>{#if caseId !== 'smoke'}<p class="case-hint">Each Home Assistant task starts with fresh synthetic state and real ha-mcp. All model sources are available.</p>{/if}{#if caseId !== 'all' && caseId !== 'smoke' && caseTiming}<p class="case-timing">Latest {caseTiming.status.replaceAll('_', ' ')} · setup {secs(caseTiming.setup_seconds)} · cleanup {secs(caseTiming.teardown_seconds)} · total {secs(caseTiming.total_wall_seconds)}</p>{/if}</div>
        <div class="field"><div class="field-head"><strong>Model source</strong><span>Choose where requests go</span></div><div class="source-grid" role="group" aria-label="Model source">
          {#each ['freetoken', 'openrouter', 'compatible'] as option (option)}<button type="button" class:selected={source === option} aria-pressed={source === option} onclick={() => chooseSource(option as Source)}><span class="symbol" aria-hidden="true">{#if option === 'freetoken'}<Radio size={22}/>{:else if option === 'openrouter'}<ArrowUpRight size={22}/>{:else}<Network size={22}/>{/if}</span><strong>{sourceNames[option as Source]}</strong><small>{option === 'freetoken' ? 'This machine' : option === 'openrouter' ? 'Hosted' : 'Private / LAN'}</small></button>{/each}
        </div></div>
        {#if source === 'compatible'}<div class="field"><div class="field-head"><label for="endpoint">OpenAI-compatible endpoint</label><span>Private HTTP /v1</span></div><div class="input-action"><input id="endpoint" type="url" bind:value={baseUrl} spellcheck="false" /><button type="button" onclick={loadModels}>Connect</button></div></div>{/if}
        <div class="field"><div class="field-head"><label for="model-search">Model</label><span>{loading ? 'Checking catalog…' : `${catalog.length} shown`}</span></div><div class="search"><Search size={17} aria-hidden="true"/><input id="model-search" placeholder={source === 'openrouter' ? 'Search OpenRouter models' : 'Filter served models'} bind:value={query} oninput={search} autocomplete="off" /></div>
          {#if catalogError}<div class="message error" role="alert">{catalogError} <button type="button" onclick={loadModels}>Retry</button></div>{:else if loading}<div class="catalog-empty">Checking available models…</div>{:else if !catalog.length}<div class="catalog-empty">{source === 'compatible' ? 'Enter an endpoint and connect to list its models.' : 'No matching models. Try another search.'}</div>{:else}<div class="model-list" role="radiogroup" aria-label="Available models">{#each catalog as option (option.id)}<label class:chosen={selectedModel === option.id}><input type="radio" name="model" value={option.id} bind:group={selectedModel} /><i></i><span><strong>{option.name}</strong><small>{option.id}</small></span>{#if option.contextLength}<em>{Math.round(option.contextLength / 1000)}K CTX</em>{/if}</label>{/each}</div>{/if}
        </div>
        {#if caseId === 'smoke'}<div class="field"><div class="field-head"><strong>Prompt treatment</strong><span>Same pinned questions</span></div><div class="variant-grid" role="group" aria-label="Prompt treatment">{#each [{ id: 'base', label: 'Base', sub: 'Original prompt' }, { id: 'careful', label: 'Careful', sub: 'Guided system note' }, { id: 'both', label: 'Compare both', sub: 'Side by side' }] as choice (choice.id)}<button type="button" class:selected={variant === choice.id} aria-pressed={variant === choice.id} onclick={() => variant = choice.id as typeof variant}><strong>{choice.label}</strong><small>{choice.sub}</small></button>{/each}</div></div>{/if}
        {#if source === 'openrouter'}<div class="paid"><h3><span>$</span> Paid run guard</h3><p>OpenRouter's workspace cap is the dollar stop. Up to {maxCalls} model calls; API retries are disabled. Each Home Assistant task also stops after 3 minutes.</p><label for="cap">Active workspace cap (USD)</label><input id="cap" type="number" min="0.01" max="20" step="0.01" bind:value={capUsd} /><label class="check"><input type="checkbox" bind:checked={capConfirmed} /> I confirm this cap is active in OpenRouter.</label>{#if !data.sources.openrouter.configured}<p class="warning">Add OPENROUTER_API_KEY to the ignored .env to enable hosted runs.</p>{/if}</div>{/if}
        <div class="run-actions"><div class="call-count"><strong>{maxCalls}</strong><small>MAX MODEL<br />CALLS</small></div><button class="run-button" type="button" disabled={!canRun} onclick={run}><span>{job?.status === 'running' ? 'RUN IN PROGRESS' : caseId === 'all' ? 'RUN EVERYTHING' : 'RUN BENCHMARK'}</span><ArrowRight size={19} aria-hidden="true"/></button></div>
        {#if runError}<div class="message error" role="alert">{runError}</div>{/if}
        {#if job}<div class:working={job.status === 'running'} class="job" role="status" aria-live="polite"><i></i><span><strong>{job.status === 'running' ? `Run ${jobPhase}` : job.status === 'complete' ? jobResults.length ? `Run finished · ${jobPassed}/${jobResults.length} passed` : 'Run finished' : job.status === 'interrupted' ? 'Run interrupted' : 'Run stopped'}</strong><small>{job.currentCaseId ? `${taskName(job.currentCaseId)} · ` : ''}{job.message || job.error || (job.totalCases ? `${job.completedCount || 0} of ${job.totalCases} steps finished` : `${sourceNames[job.source]} · ${short(job.model)}`)}</small>{#if job.totalCases}<span class="progress-track" role="progressbar" aria-label="Benchmark progress" aria-valuemin="0" aria-valuemax={job.totalCases} aria-valuenow={job.completedCount || 0}><i style:transform={`scaleX(${jobProgress / 100})`}></i></span>{/if}{#if job.completedCases?.length}<span class="case-status-list">{#each job.completedCases as done (done.caseId)}<span class:failed={done.status === 'failed' || done.passed === false}>{done.status === 'failed' ? 'ERROR' : done.passed === true ? 'PASS' : done.passed === false ? 'FAIL' : 'DONE'} · {taskName(done.caseId)}{done.modelCalls !== undefined ? ` · ${done.modelCalls} calls` : ''}</span>{/each}</span>{/if}</span>{#if job.status !== 'running'}<button type="button" onclick={refresh}>Refresh</button>{/if}</div>{/if}
      </section>
      <section class="report-panel" id="report" aria-labelledby="report-title">
        <div class:hidden-view={activeView === 'activity'}>
        <div class="section-head"><div><h2 id="report-title">The scorecard<span>.</span></h2><p>All pinned fixture cases. Missing outcomes stay marked NOT RUN.</p></div><b>LIVE DATA</b></div>
        <div class="note"><Info size={17} aria-hidden="true"/> These pilot cases screen the workflow. A few tasks cannot establish broad model superiority.</div>
        <div class="report-toolbar"><strong>RUN RESULTS</strong><div role="group" aria-label="Filter results"><button class:selected={filter === 'all'} onclick={() => filter = 'all'}>All</button><button class:selected={filter === 'local'} onclick={() => filter = 'local'}>Local</button><button class:selected={filter === 'hosted'} onclick={() => filter = 'hosted'}>Hosted</button></div></div>
        {#if selectedReportRun}<div class="run-picker"><label for="report-run">Choose a run</label><select id="report-run" value={selectedReportRun.key} onchange={(event) => { selectedReportRunKey = event.currentTarget.value; selectedKey = ''; }}>{#each reportRuns as run (run.key)}<option value={run.key}>{runLabel(run)}</option>{/each}</select><div class="run-picker-summary"><strong>{name(selectedReportRun.model)}</strong><span>{runTime(selectedReportRun.startedAt)} · {selectedReportRun.prompts} prompt · {runScore(selectedReportRun)}{selectedReportRun.unscored ? ` · ${selectedReportRun.unscored} unscored` : ''}</span></div></div>{/if}
        {#if matrix.length}
          <div class="matrix-wrap"><table><thead><tr><th scope="col">Model / prompt</th><th scope="col">Score</th><th scope="col">Calls</th><th scope="col">Model time</th><th scope="col">Setup</th><th scope="col">Cleanup</th><th scope="col">Tokens</th><th scope="col">Cost</th></tr></thead><tbody>
            {#each matrix as entry (entry.key)}
              <tr><th scope="row"><strong>{short(entry.model)}</strong><small>{route(entry.model)} · {entry.prompt} prompt · {entry.runId}</small><button class="detail-link" type="button" aria-expanded={selectedKey === entry.key} onclick={() => selectedKey = selectedKey === entry.key ? '' : entry.key}>Run details</button></th>
                <td><div class="score"><strong>{entry.scored ? `${entry.pass}/${entry.scored}` : '—'}</strong><span><i style:width={`${entry.scored ? entry.pass / entry.scored * 100 : 0}%`}></i></span></div></td><td class="numeric">{entry.calls === null ? '—' : entry.calls}</td><td class="numeric">{secs(entry.time)}</td><td class="numeric">{entry.setup ? secs(entry.setup) : '—'}</td><td class="numeric">{entry.cleanup ? secs(entry.cleanup) : '—'}</td><td class="numeric">{fmt(entry.tokens)}</td><td class="numeric">{entry.cost === null ? '—' : `$${entry.cost.toFixed(6)}`}</td>
              </tr>
            {/each}
          </tbody></table></div>
        {:else}<div class="empty"><div aria-hidden="true">×</div><strong>No runs in this view yet.</strong><p>Choose another source filter, or run a pinned benchmark to see its task results here.</p></div>{/if}
        {#if selectedRun}
          <div class="run-detail" aria-label="Selected run details"><div class="detail-head"><h3>Run details</h3><button type="button" onclick={() => selectedKey = ''}>Close</button></div><div class="detail-cases"><strong>Task outcomes</strong>{#each availableCases as benchmark (benchmark.id)}{@const result = selectedRun.cases[benchmark.id]}{#if result}<div><span>{benchmark.name}</span><b class:pass={result.passed === true} class:miss={result.passed === false}>{result.passed === true ? 'PASS' : result.passed === false ? 'FAIL' : 'UNSCORED'}</b><small>{result.model_calls ?? '—'} calls · {secs(result.latency_seconds)}{result.score_metadata?.synthetic_ha_state?.state_correct === true ? ' · Final state reached' : ''}{result.score_metadata?.synthetic_ha_state?.trace_valid === false ? ' · Tool sequence failed' : ''}{result.score_explanation ? ` · ${result.score_explanation}` : ''}</small></div>{/if}{/each}</div><dl>
            <div><dt>Exact model ID</dt><dd>{name(selectedRun.model)}</dd></div><div><dt>Source</dt><dd>{route(selectedRun.model)}</dd></div>
            <div><dt>Prompt</dt><dd>{selectedRun.prompt}</dd></div><div><dt>Run ID</dt><dd>{selectedRun.sample.launcher_run_id || selectedRun.sample.run_id}</dd></div>
            <div><dt>Routed model</dt><dd>{selectedRun.routedModels.join(', ') || selectedRun.sample.concrete_response_model || 'Not reported'}</dd></div><div><dt>Providers</dt><dd>{selectedRun.providers.join(', ') || 'Not reported'}</dd></div><div><dt>Started</dt><dd>{selectedRun.sample.started_at || 'Not reported'}</dd></div>
            <div><dt>Inference</dt><dd>Temperature {selectedRun.sample.inference?.temperature ?? '—'} · max {selectedRun.sample.inference?.max_tokens ?? '—'} tokens · {selectedRun.sample.inference?.max_retries ?? '—'} retries · {selectedRun.sample.inference?.timeout ?? '—'}s timeout</dd></div>
            <div><dt>Fixture / version</dt><dd>{selectedRun.sample.fixture || '—'} · task v{selectedRun.sample.task_version || '—'} · Inspect {selectedRun.sample.inspect_version || '—'}</dd></div>
            <div><dt>Inspect log</dt><dd>{selectedRun.sample.log_file || 'Not reported'}</dd></div>
            {#if selectedRun.sample.run_timing}<div><dt>Container setup / cleanup</dt><dd>{secs(selectedRun.sample.run_timing.setup_seconds)} / {secs(selectedRun.sample.run_timing.teardown_seconds)}</dd></div><div><dt>Evaluation / wall time</dt><dd>{secs(selectedRun.sample.run_timing.evaluation_seconds)} / {secs(selectedRun.sample.run_timing.total_wall_seconds)}</dd></div>{/if}
          </dl></div>
        {/if}
        </div><div class="activity" class:hidden-view={activeView !== 'activity'} id="activity"><div class="activity-head"><h3>Activity</h3><span>{activityRuns.length} {activityRuns.length === 1 ? 'RUN' : 'RUNS'}</span></div>{#if selectedActivityRun}<div class="run-picker"><label for="activity-run">Choose a run</label><select id="activity-run" value={selectedActivityRun.key} onchange={(event) => selectedActivityRunKey = event.currentTarget.value}>{#each activityRuns as run (run.key)}<option value={run.key}>{runLabel(run)}</option>{/each}</select><div class="run-picker-summary"><strong>{name(selectedActivityRun.model)}</strong><span>{runTime(selectedActivityRun.startedAt)} · {selectedActivityRun.prompts} prompt · {runScore(selectedActivityRun)}{selectedActivityRun.unscored ? ` · ${selectedActivityRun.unscored} unscored` : ''}</span><small>Run {selectedActivityRun.runId} · {selectedActivityRun.rows.length} task {selectedActivityRun.rows.length === 1 ? 'record' : 'records'}</small></div></div>{#each selectedActivityRun.rows as row (`${row.run_id}-${row.sample_id}-${row.prompt_variant}`)}<div class="activity-row"><i class:good={row.passed === true} class:bad={row.passed === false}></i><div><strong>{taskName(row.sample_id)}</strong><small>{row.prompt_variant} prompt · {runTime(row.started_at || '')}{row.score_explanation ? ` · ${row.score_explanation}` : ''}</small></div><aside><strong>{row.passed === true ? 'PASS' : row.passed === false ? 'FAIL' : 'UNSCORED'}</strong><small>{secs(row.latency_seconds)} · {row.model_calls ?? '—'} calls · {fmt(tokens(row))} tok</small></aside></div>{/each}{:else}<p class="activity-empty">Run a benchmark to build an activity trail.</p>{/if}</div>
      </section>
    </div>
    <footer><span>mattbench / personal evaluation lab</span><span>Fixtures and scores stay pinned. Raw traces stay local.</span></footer>
  </main>
</div>
