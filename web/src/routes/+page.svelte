<script lang="ts">
  import { onMount } from 'svelte';
  import { ArrowUpRight, ChartNoAxesCombined, Clock3, Radio, Network, Search, ArrowRight, Info, ChevronDown, Check } from '@lucide/svelte';
  import type { PageProps } from './$types';
  import type { Source, ModelOption as Model, Row, BenchmarkCase, CaseTiming, Job } from '../lib/contracts';
  import { parseHistory, parseJob, parseOverview } from '../lib/contracts';
  import { groupRuns, matrixRuns, tokens, type RecordedRun } from '../lib/results';
  import { startPolling } from '../lib/polling';
  import ConsoleStatus from '../lib/ConsoleStatus.svelte';
  import JobStatus from '../lib/JobStatus.svelte';
  import PaidGuard from '../lib/PaidGuard.svelte';
  import BillingStatus from '../lib/BillingStatus.svelte';
  import './console.css';

  let { data }: PageProps = $props();
  let rows = $state.raw<Row[]>([]);
  let observedJob = $state.raw<Job | null | undefined>(undefined);
  let job = $derived(observedJob === undefined ? data.job : observedJob);
  let timings = $state.raw<CaseTiming[]>([]);
  let warnings = $state.raw<string[]>([]);
  let connectionError = $state('');
  let historyError = $state('');
  let loadedRevision = $state('');
  let jobGeneration = 0;
  let polling: { stop: () => void; wake: () => void } | undefined;
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
  let selectedReportRunKey = $state('');
  let selectedActivityRunKey = $state('');
  let searchTimer: ReturnType<typeof setTimeout>;
  let catalogRequest = 0;
  const sourceNames: Record<Source, string> = { freetoken: 'FreeToken', openrouter: 'OpenRouter', compatible: 'Other endpoint' };
  let availableCases = $derived(data.cases as BenchmarkCase[]);
  type CategoryId = 'smart_home' | 'laptop_shopping' | 'smoke';
  interface CategoryInfo {
    id: CategoryId;
    label: string;
    description: string;
    badge: string;
    cases: BenchmarkCase[];
  }
  let selectionMode = $state<'all' | 'categories'>('all');
  let selectedCategoryIds = $state<CategoryId[]>([]);
  let accordionOpen = $state(false);
  let categories = $derived.by<CategoryInfo[]>(() => {
    const smartHomeCases = availableCases.filter((c) => c.category === 'smart_home' || c.suite === 'ha');
    const laptopCases = availableCases.filter((c) => c.category === 'laptop_shopping' || c.suite === 'laptop');
    const smokeCases = availableCases.filter((c) => c.suite === 'smoke');
    return [
      {
        id: 'smart_home',
        label: 'Smart home',
        description: 'Reading lamp and MXZ coordinator (real ha-mcp in synthetic home)',
        badge: 'SMART HOME',
        cases: smartHomeCases
      },
      {
        id: 'laptop_shopping',
        label: 'Laptop shopping',
        description: '10-laptop specs & pictures, 10 user personas, and trick questions (ALL / NONE)',
        badge: 'LAPTOP',
        cases: laptopCases
      },
      {
        id: 'smoke',
        label: 'Smoke questions',
        description: 'Pinned quick reasoning checks (strawberry count, car wash transport)',
        badge: 'SMOKE',
        cases: smokeCases
      }
    ];
  });
  function selectAll() {
    selectionMode = 'all';
    selectedCategoryIds = [];
  }
  function toggleCategory(catId: CategoryId) {
    selectionMode = 'categories';
    if (selectedCategoryIds.includes(catId)) {
      selectedCategoryIds = selectedCategoryIds.filter((id) => id !== catId);
    } else {
      selectedCategoryIds = [...selectedCategoryIds, catId];
    }
  }
  let visibleCases = $derived.by(() => {
    if (selectionMode === 'all') return availableCases;
    return availableCases.filter((c) => {
      if (selectedCategoryIds.includes('smart_home') && (c.category === 'smart_home' || c.suite === 'ha')) return true;
      if (selectedCategoryIds.includes('laptop_shopping') && (c.category === 'laptop_shopping' || c.suite === 'laptop')) return true;
      if (selectedCategoryIds.includes('smoke') && c.suite === 'smoke') return true;
      return false;
    });
  });
  let caseTiming = $derived(timings.find((entry) => entry.case_id === caseId));
  let smokeCallCap = $derived(availableCases.filter((entry) => entry.suite === 'smoke').reduce((sum, entry) => sum + entry.maxModelCalls, 0));
  let activeCaseId = $derived.by(() => {
    if (selectionMode === 'all') return 'all';
    if (selectedCategoryIds.length === 0) return '';
    if (selectedCategoryIds.length === categories.length) return 'all';
    if (selectedCategoryIds.length === 1) {
      if (selectedCategoryIds[0] === 'smart_home') return 'smart_home';
      if (selectedCategoryIds[0] === 'laptop_shopping') return 'laptop';
      if (selectedCategoryIds[0] === 'smoke') return 'smoke';
    }
    return selectedCategoryIds.join(',');
  });
  let caseId = $derived(activeCaseId);
  let maxCalls = $derived.by(() => {
    if (selectionMode === 'all') {
      return availableCases.reduce((sum, entry) => sum + entry.maxModelCalls, 0);
    }
    if (selectedCategoryIds.length === 1 && selectedCategoryIds[0] === 'smoke') {
      return smokeCallCap * (variant === 'both' ? 2 : 1);
    }
    return visibleCases.reduce((sum, entry) => sum + entry.maxModelCalls, 0);
  });
  // OpenRouter marks zero-cost endpoints with the ':free' model-ID suffix; the paid guard only gates paid runs.
  let paidRun = $derived(!selectedModel.endsWith(':free'));
  let canRun = $derived(Boolean(selectedModel) && maxCalls > 0 && !loading && job?.status !== 'running' && (source !== 'openrouter' || (data.sources.openrouter.configured && (!paidRun || (capConfirmed && capUsd > 0 && capUsd <= 20)))));
  function name(model: string) { return model.replace(/^openai-api\/(freetoken|openrouter|compatible)\//, ''); }
  function short(model: string) { const text = name(model); return text.length > 31 ? `${text.slice(0, 29)}…` : text; }
  function route(model: string) { return model.startsWith('openai-api/openrouter/') ? 'OpenRouter' : model.startsWith('openai-api/compatible/') ? 'Other endpoint' : 'FreeToken'; }
  function fmt(value: number) { return new Intl.NumberFormat('en-US').format(value); }
  function secs(value?: number) { return value == null ? '—' : `${value.toFixed(value < 10 ? 1 : 0)}s`; }
  function taskName(id: string) { return availableCases.find((entry) => entry.id === id)?.name || id.replaceAll('_', ' '); }
  function runTime(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Time not reported' : new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short'
    }).format(date);
  }
  let runs = $derived(groupRuns(rows));
  function runScore(run: RecordedRun) { return run.scored ? `${run.pass} of ${run.scored} passed` : 'No scored tasks'; }
  function runLabel(run: RecordedRun) { return `${runTime(run.startedAt)} · ${name(run.model)} · ${runScore(run)}`; }
  let reportRuns = $derived(runs.filter((run) => run.rows.some((row) => availableCases.some((entry) => entry.id === row.sample_id)) && (filter === 'all' || (filter === 'hosted' ? route(run.model) === 'OpenRouter' : route(run.model) !== 'OpenRouter'))));
  let activityRuns = $derived(runs);
  let selectedReportRun = $derived(reportRuns.find((run) => run.key === selectedReportRunKey) || reportRuns[0]);
  let selectedActivityRun = $derived(activityRuns.find((run) => run.key === selectedActivityRunKey) || activityRuns[0]);
  let matrix = $derived(matrixRuns((selectedReportRun?.rows || []).filter((entry) => availableCases.some((benchmark) => benchmark.id === entry.sample_id))));
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
  function syncView() {
    const view = location.hash.slice(1);
    activeView = view === 'report' ? 'results' : view === 'activity' ? 'activity' : 'run';
    polling?.wake();
  }
  async function refresh(signal: AbortSignal) {
    const generation = jobGeneration;
    const response = await fetch('/api/overview', { cache: 'no-store', signal });
    if (!response.ok) throw new Error(`Job status returned HTTP ${response.status}.`);
    const body = parseOverview(await response.json());
    if (signal.aborted) return;
    if (generation === jobGeneration) observedJob = body.job;
    if (activeView === 'run' || loadedRevision === body.revision) return;
    try {
      const result = await fetch(`/api/history?${new URLSearchParams({ revision: loadedRevision })}`, { cache: 'no-store', signal });
      if (result.status === 304) return;
      if (!result.ok) throw new Error(`History returned HTTP ${result.status}.`);
      const history = parseHistory(await result.json());
      if (signal.aborted) return;
      rows = history.rows;
      timings = history.runTimings;
      warnings = history.warnings;
      loadedRevision = history.revision;
      historyError = '';
    } catch (cause) {
      if (signal.aborted) throw cause;
      historyError = cause instanceof Error ? cause.message : 'History could not be loaded.';
      throw cause;
    }
  }
  async function run() {
    runError = '';
    jobGeneration += 1;
    try {
      const response = await fetch('/api/runs', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ source, model: selectedModel, variant: caseId === 'smoke' ? variant : 'base', caseId, baseUrl: source === 'compatible' ? baseUrl : undefined, maxCalls, capUsd: source === 'openrouter' && paidRun ? capUsd : undefined, capConfirmed: source === 'openrouter' && paidRun ? capConfirmed : undefined }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || 'Could not start run.');
      jobGeneration += 1;
      observedJob = parseJob(body.job);
      polling?.wake();
    } catch (cause) { runError = cause instanceof Error ? cause.message : 'Could not start run.'; }
  }
  onMount(() => {
    syncView();
    window.addEventListener('hashchange', syncView);
    void loadModels();
    polling = startPolling({
      poll: refresh,
      interval: () => document.hidden ? 60000 : job?.status === 'running' ? 1800 : 15000,
      onError: (message) => connectionError = message
    });
    const visible = () => { if (!document.hidden) polling?.wake(); };
    document.addEventListener('visibilitychange', visible);
    return () => {
      window.removeEventListener('hashchange', syncView);
      document.removeEventListener('visibilitychange', visible);
      polling?.stop();
      clearTimeout(searchTimer);
    };
  });
</script>

<div class="shell">
  <aside class="rail" aria-label="Primary navigation">
    <a class="brand" href="#top" aria-label="mattbench home"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>matt<span>bench</span></a>
    <nav><a class:active={activeView === 'run'} href="#run" aria-current={activeView === 'run' ? 'page' : undefined}><ArrowUpRight size={19} aria-hidden="true"/>Run a benchmark</a><a class:active={activeView === 'results'} href="#report" aria-current={activeView === 'results' ? 'page' : undefined}><ChartNoAxesCombined size={19} aria-hidden="true"/>Results</a><a class:active={activeView === 'activity'} href="#activity" aria-current={activeView === 'activity' ? 'page' : undefined}><Clock3 size={19} aria-hidden="true"/>Activity</a></nav>
    <div class="rail-foot"><i></i> LOCAL CONSOLE</div>
  </aside>
  <main id="top">
    <header class="console-header"><h1>Benchmark console<span>.</span></h1><div class="console-facts"><span><strong>{availableCases.length}</strong> pinned cases</span><span><strong>{loadedRevision ? runs.length : '—'}</strong> {loadedRevision ? 'recorded runs' : 'history on demand'}</span><span>Inspect AI</span></div></header>
    <ConsoleStatus {connectionError} {historyError} {warnings} />
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
        <div class="field case-field">
          <div class="field-head">
            <strong>Choose a benchmark</strong>
            <span>{availableCases.length} total tasks across {categories.length} categories</span>
          </div>
          <div class="case-selection-wrapper">
            <button
              class="case-option everything"
              class:selected={selectionMode === 'all'}
              type="button"
              aria-pressed={selectionMode === 'all'}
              onclick={selectAll}
            >
              <span>
                <strong>Run everything</strong>
                <small>All {availableCases.length} tasks: Smoke questions, Smart home, and Laptop shopping</small>
              </span>
              <b>{availableCases.length} TASKS</b>
            </button>

            <div class="category-accordion-card">
              <button
                class="category-accordion-trigger"
                class:active={selectionMode === 'categories'}
                type="button"
                aria-expanded={accordionOpen}
                onclick={() => accordionOpen = !accordionOpen}
              >
                <div class="trigger-label">
                  <span class="trigger-title">
                    <strong>Select by category</strong>
                    {#if selectionMode === 'categories' && selectedCategoryIds.length > 0}
                      <span class="active-pill">{selectedCategoryIds.length} of {categories.length} SELECTED</span>
                    {/if}
                  </span>
                  <small>Smart home, Laptop shopping, and Smoke questions</small>
                </div>
                <div class="trigger-meta">
                  <span class="mode-badge">{selectionMode === 'categories' ? `${selectedCategoryIds.length} ACTIVE` : 'CATEGORIES'}</span>
                  <span class="chevron" class:open={accordionOpen} aria-hidden="true"><ChevronDown size={18} /></span>
                </div>
              </button>

              {#if accordionOpen}
                <div class="category-accordion-body" role="group" aria-label="Category multi-choice selection">
                  <p class="category-note">Select one or more categories below (mutually exclusive with Run Everything):</p>
                  <div class="category-choices">
                    {#each categories as cat (cat.id)}
                      {@const isChecked = selectionMode === 'categories' && selectedCategoryIds.includes(cat.id)}
                      <div class="category-card" class:checked={isChecked}>
                        <label class="category-choice-header">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onchange={() => toggleCategory(cat.id)}
                          />
                          <span class="choice-checkbox" aria-hidden="true">
                            {#if isChecked}<Check size={14} />{/if}
                          </span>
                          <div class="choice-text">
                            <div class="choice-title-row">
                              <strong>{cat.label}</strong>
                              <span class="category-badge">{cat.badge}</span>
                            </div>
                            <small>{cat.description}</small>
                          </div>
                          <b class="task-count">{cat.cases.length} {cat.cases.length === 1 ? 'TASK' : 'TASKS'}</b>
                        </label>

                        {#if cat.id === 'smart_home'}
                          <div class="category-subtasks">
                            <span class="subtasks-label">Included tasks:</span>
                            <ul>
                              {#each cat.cases as sc (sc.id)}
                                <li>
                                  <code>{sc.name}</code>
                                  <span>{sc.maxModelCalls} calls max · real ha-mcp</span>
                                </li>
                              {/each}
                            </ul>
                          </div>
                        {/if}
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          </div>

          {#if selectionMode === 'categories' && selectedCategoryIds.length === 0}
            <p class="case-hint warning">No categories selected. Check at least one category above, or select "Run everything".</p>
          {:else if selectionMode === 'categories' && selectedCategoryIds.includes('smart_home')}
            <p class="case-hint">Smart home tasks start with fresh synthetic state and real ha-mcp. All model sources are available.</p>
          {:else if selectionMode === 'all'}
            <p class="case-hint">Running everything evaluates smoke reasoning, smart home automation with real ha-mcp, and laptop shopping personas.</p>
          {/if}

          {#if caseTiming}
            <p class="case-timing">Latest {caseTiming.status.replaceAll('_', ' ')} · setup {secs(caseTiming.setup_seconds)} · cleanup {secs(caseTiming.teardown_seconds)} · total {secs(caseTiming.total_wall_seconds)}</p>
          {/if}
        </div>
        <div class="field"><div class="field-head"><strong>Model source</strong><span>Choose where requests go</span></div><div class="source-grid" role="group" aria-label="Model source">
          {#each ['freetoken', 'openrouter', 'compatible'] as option (option)}<button type="button" class:selected={source === option} aria-pressed={source === option} onclick={() => chooseSource(option as Source)}><span class="symbol" aria-hidden="true">{#if option === 'freetoken'}<Radio size={22}/>{:else if option === 'openrouter'}<ArrowUpRight size={22}/>{:else}<Network size={22}/>{/if}</span><strong>{sourceNames[option as Source]}</strong><small>{option === 'freetoken' ? 'This machine' : option === 'openrouter' ? 'Hosted' : 'Private / LAN'}</small></button>{/each}
        </div></div>
        {#if source === 'compatible'}<div class="field"><div class="field-head"><label for="endpoint">OpenAI-compatible endpoint</label><span>Private HTTP /v1</span></div><div class="input-action"><input id="endpoint" type="url" bind:value={baseUrl} spellcheck="false" /><button type="button" onclick={loadModels}>Connect</button></div></div>{/if}
        <div class="field"><div class="field-head"><label for="model-search">Model</label><span>{loading ? 'Checking catalog…' : `${catalog.length} shown`}</span></div><div class="search"><Search size={17} aria-hidden="true"/><input id="model-search" placeholder={source === 'openrouter' ? 'Search OpenRouter models' : 'Filter served models'} bind:value={query} oninput={search} autocomplete="off" /></div>
          {#if catalogError}<div class="message error" role="alert">{catalogError} <button type="button" onclick={loadModels}>Retry</button></div>{:else if loading}<div class="catalog-empty">Checking available models…</div>{:else if !catalog.length}<div class="catalog-empty">{source === 'compatible' ? 'Enter an endpoint and connect to list its models.' : 'No matching models. Try another search.'}</div>{:else}<div class="model-list" role="radiogroup" aria-label="Available models">{#each catalog as option (option.id)}<label class:chosen={selectedModel === option.id}><input type="radio" name="model" value={option.id} bind:group={selectedModel} /><i></i><span><strong>{option.name}</strong><small>{option.id}</small></span>{#if option.contextLength}<em>{Math.round(option.contextLength / 1000)}K CTX</em>{/if}</label>{/each}</div>{/if}
        </div>
        {#if caseId === 'smoke'}<div class="field"><div class="field-head"><strong>Prompt treatment</strong><span>Same pinned questions</span></div><div class="variant-grid" role="group" aria-label="Prompt treatment">{#each [{ id: 'base', label: 'Base', sub: 'Original prompt' }, { id: 'careful', label: 'Careful', sub: 'Guided system note' }, { id: 'both', label: 'Compare both', sub: 'Side by side' }] as choice (choice.id)}<button type="button" class:selected={variant === choice.id} aria-pressed={variant === choice.id} onclick={() => variant = choice.id as typeof variant}><strong>{choice.label}</strong><small>{choice.sub}</small></button>{/each}</div></div>{/if}
        {#if source === 'openrouter' && (paidRun || !data.sources.openrouter.configured)}<PaidGuard {maxCalls} configured={data.sources.openrouter.configured} paid={paidRun} bind:capUsd bind:capConfirmed />{/if}
        <div class="run-actions"><div class="call-count"><strong>{maxCalls}</strong><small>MAX MODEL<br />CALLS</small></div><button class="run-button" type="button" disabled={!canRun} onclick={run}><span>{job?.status === 'running' ? 'RUN IN PROGRESS' : caseId === 'all' ? 'RUN EVERYTHING' : 'RUN BENCHMARK'}</span><ArrowRight size={19} aria-hidden="true"/></button></div>
        {#if runError}<div class="message error" role="alert">{runError}</div>{/if}
        {#if job}<JobStatus {job} resultsCount={jobResults.length} passedCount={jobPassed} {taskName} refresh={() => polling?.wake()} />{/if}
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
        {:else if !loadedRevision}
          <div class="empty">
            <strong>{activeView === 'run' ? 'Results load on demand.' : historyError ? 'Results could not be loaded.' : 'Loading result history…'}</strong>
            {#if activeView === 'run'}<p><a href="#report">Open Results</a> to read local run history.</p>{/if}
          </div>
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
          <BillingStatus rows={Object.values(selectedRun.cases)} />
        {/if}
        </div><div class="activity" class:hidden-view={activeView !== 'activity'} id="activity"><div class="activity-head"><h3>Activity</h3><span>{activityRuns.length} {activityRuns.length === 1 ? 'RUN' : 'RUNS'}</span></div>{#if selectedActivityRun}<div class="run-picker"><label for="activity-run">Choose a run</label><select id="activity-run" value={selectedActivityRun.key} onchange={(event) => selectedActivityRunKey = event.currentTarget.value}>{#each activityRuns as run (run.key)}<option value={run.key}>{runLabel(run)}</option>{/each}</select><div class="run-picker-summary"><strong>{name(selectedActivityRun.model)}</strong><span>{runTime(selectedActivityRun.startedAt)} · {selectedActivityRun.prompts} prompt · {runScore(selectedActivityRun)}{selectedActivityRun.unscored ? ` · ${selectedActivityRun.unscored} unscored` : ''}</span><small>Run {selectedActivityRun.runId} · {selectedActivityRun.rows.length} task {selectedActivityRun.rows.length === 1 ? 'record' : 'records'}</small></div></div>{#each selectedActivityRun.rows as row (`${row.run_id}-${row.sample_id}-${row.prompt_variant}`)}<div class="activity-row"><i class:good={row.passed === true} class:bad={row.passed === false}></i><div><strong>{taskName(row.sample_id)}</strong><small>{row.prompt_variant} prompt · {runTime(row.started_at || '')}{row.score_explanation ? ` · ${row.score_explanation}` : ''}</small></div><aside><strong>{row.passed === true ? 'PASS' : row.passed === false ? 'FAIL' : 'UNSCORED'}</strong><small>{secs(row.latency_seconds)} · {row.model_calls ?? '—'} calls · {fmt(tokens(row))} tok</small></aside></div>{/each}{:else}<p class="activity-empty">Run a benchmark to build an activity trail.</p>{/if}</div>
      </section>
    </div>
    <footer><span>mattbench / personal evaluation lab</span><span>Fixtures and scores stay pinned. Raw traces stay local.</span></footer>
  </main>
</div>
