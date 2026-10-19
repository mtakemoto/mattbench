<script lang="ts">
  import { onMount } from 'svelte';
  import { ArrowUpRight, ChartNoAxesCombined, Clock3, Radio, Network, Search, ArrowRight } from '@lucide/svelte';
  import type { PageProps } from './$types';
  import { parseHistory, parseJob, parseOverview, SELECT_ALL, SOURCES, type Job, type ModelOption, type Row, type Source } from '../lib/contracts';
  import { SOURCE_LABELS, taskNamer } from '../lib/format';
  import { groupRuns } from '../lib/results';
  import { startPolling } from '../lib/polling';
  import ActivityLog from '../lib/ActivityLog.svelte';
  import ConsoleStatus from '../lib/ConsoleStatus.svelte';
  import JobStatus from '../lib/JobStatus.svelte';
  import LiveRun from '../lib/LiveRun.svelte';
  import PaidGuard from '../lib/PaidGuard.svelte';
  import PromptPicker from '../lib/PromptPicker.svelte';
  import Scorecard from '../lib/Scorecard.svelte';
  import SuitePicker from '../lib/SuitePicker.svelte';
  import './console.css';

  type View = 'run' | 'results' | 'activity';
  const SOURCE_HINTS: Record<Source, string> = { freetoken: 'This machine', openrouter: 'Hosted', compatible: 'Private / LAN' };

  let { data }: PageProps = $props();

  // Result history and the active job, refreshed by polling.
  let rows = $state.raw<Row[]>([]);
  let warnings = $state.raw<string[]>([]);
  let observedJob = $state.raw<Job | null | undefined>(undefined);
  let job = $derived(observedJob === undefined ? data.job : observedJob);
  let connectionError = $state('');
  let historyError = $state('');
  let loadedRevision = $state('');
  let jobGeneration = 0;
  let polling: { stop: () => void; wake: () => void } | undefined;
  let activeView = $state<View>('run');

  // Run setup.
  let source = $state<Source>('freetoken');
  let baseUrl = $state('http://127.0.0.1:11434/v1');
  let query = $state('');
  let catalog = $state.raw<ModelOption[]>([]);
  let selectedModel = $state('');
  let loading = $state(false);
  let catalogError = $state('');
  let runError = $state('');
  let capUsd = $state(20);
  let capConfirmed = $state(false);
  let selection = $state<string[]>([SELECT_ALL]);
  let variants = $state<string[]>(['base']);
  let searchTimer: ReturnType<typeof setTimeout>;
  let catalogRequest = 0;

  let suites = $derived(data.suites);
  let allCases = $derived(suites.flatMap((suite) => suite.cases));
  let taskName = $derived(taskNamer(suites));
  let selectedSuites = $derived(selection.includes(SELECT_ALL) ? suites : suites.filter((suite) => selection.includes(suite.id)));
  // Only variants every selected suite supports can be offered.
  let variantOptions = $derived(selectedSuites.length
    ? selectedSuites.map((suite) => suite.variants).reduce((shared, next) => shared.filter((variant) => next.includes(variant)))
    : ['base']);
  let supportedVariants = $derived(variants.filter((variant) => variantOptions.includes(variant)));
  let runVariants = $derived(supportedVariants.length ? supportedVariants : ['base']);
  let selectedCases = $derived(selectedSuites.flatMap((suite) => suite.cases));
  let maxCalls = $derived(selectedCases.reduce((sum, entry) => sum + entry.maxModelCalls, 0) * runVariants.length);
  // OpenRouter marks zero-cost endpoints with the ':free' model-ID suffix; the paid guard only gates paid runs.
  let paidRun = $derived(!selectedModel.endsWith(':free'));
  let openrouterAllowed = $derived(source !== 'openrouter' || (data.sources.openrouter.configured && (!paidRun || (capConfirmed && capUsd > 0 && capUsd <= 20))));
  let canRun = $derived(Boolean(selectedModel) && maxCalls > 0 && !loading && job?.status !== 'running' && openrouterAllowed);

  let runs = $derived(groupRuns(rows));
  let caseIds = $derived(new Set(allCases.map((entry) => entry.id)));
  let jobResults = $derived(rows.filter((row) => row.launcher_run_id === job?.id && caseIds.has(row.sample_id)));
  let jobPassed = $derived(jobResults.filter((row) => row.passed === true).length);

  function catalogFailure(reason: string): string {
    if (reason !== 'fetch failed') return reason;
    return source === 'freetoken' ? 'FreeToken is unavailable. Start it and retry.'
      : source === 'compatible' ? 'Could not reach this endpoint. Check its address and retry.'
      : 'Could not reach OpenRouter. Retry in a moment.';
  }
  async function loadModels() {
    const requestId = ++catalogRequest;
    loading = true;
    catalogError = '';
    try {
      const params = new URLSearchParams({ source, q: query });
      if (source === 'compatible') params.set('baseUrl', baseUrl);
      const response = await fetch(`/api/models?${params}`);
      const body = await response.json();
      if (requestId !== catalogRequest) return;
      if (!response.ok) throw new Error(body.error || 'Catalog unavailable.');
      catalog = body.models;
      if (!catalog.some((option) => option.id === selectedModel)) {
        selectedModel = source === 'freetoken' ? catalog.find((option) => option.id === data.sources.freetoken.defaultModel)?.id || catalog[0]?.id || '' : '';
      }
    } catch (cause) {
      if (requestId !== catalogRequest) return;
      catalog = [];
      selectedModel = '';
      catalogError = catalogFailure(cause instanceof Error ? cause.message : 'Catalog unavailable.');
    } finally {
      if (requestId === catalogRequest) loading = false;
    }
  }
  function chooseSource(next: Source) {
    ++catalogRequest;
    source = next; query = ''; selectedModel = ''; catalog = []; catalogError = ''; runError = ''; loading = false;
    if (next !== 'compatible') void loadModels();
  }
  function search() { clearTimeout(searchTimer); searchTimer = setTimeout(() => void loadModels(), 260); }
  function syncView() {
    const view = location.hash.slice(1);
    activeView = view === 'report' ? 'results' : view === 'activity' ? 'activity' : 'run';
    polling?.wake();
  }
  async function loadHistory(signal: AbortSignal) {
    try {
      const response = await fetch(`/api/history?${new URLSearchParams({ revision: loadedRevision })}`, { cache: 'no-store', signal });
      if (response.status === 304) return;
      if (!response.ok) throw new Error(`History returned HTTP ${response.status}.`);
      const history = parseHistory(await response.json());
      if (signal.aborted) return;
      rows = history.rows;
      warnings = history.warnings;
      loadedRevision = history.revision;
      historyError = '';
    } catch (cause) {
      if (!signal.aborted) historyError = cause instanceof Error ? cause.message : 'History could not be loaded.';
      throw cause;
    }
  }
  async function refresh(signal: AbortSignal) {
    const generation = jobGeneration;
    const response = await fetch('/api/overview', { cache: 'no-store', signal });
    if (!response.ok) throw new Error(`Job status returned HTTP ${response.status}.`);
    const body = parseOverview(await response.json());
    if (signal.aborted) return;
    if (generation === jobGeneration) observedJob = body.job;
    if (activeView !== 'run' && loadedRevision !== body.revision) await loadHistory(signal);
  }
  async function run() {
    runError = '';
    jobGeneration += 1;
    const paid = source === 'openrouter' && paidRun;
    try {
      const response = await fetch('/api/runs', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          source, model: selectedModel, selection, variants: runVariants, maxCalls,
          baseUrl: source === 'compatible' ? baseUrl : undefined,
          capUsd: paid ? capUsd : undefined, capConfirmed: paid ? capConfirmed : undefined
        })
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || 'Could not start run.');
      jobGeneration += 1;
      observedJob = parseJob(body.job);
      polling?.wake();
    } catch (cause) {
      runError = cause instanceof Error ? cause.message : 'Could not start run.';
    }
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
    <nav>
      <a class:active={activeView === 'run'} href="#run" aria-current={activeView === 'run' ? 'page' : undefined}><ArrowUpRight size={19} aria-hidden="true"/>Run a benchmark</a>
      <a class:active={activeView === 'results'} href="#report" aria-current={activeView === 'results' ? 'page' : undefined}><ChartNoAxesCombined size={19} aria-hidden="true"/>Results</a>
      <a class:active={activeView === 'activity'} href="#activity" aria-current={activeView === 'activity' ? 'page' : undefined}><Clock3 size={19} aria-hidden="true"/>Activity</a>
    </nav>
    <div class="rail-foot"><i></i> LOCAL CONSOLE</div>
  </aside>
  <main id="top">
    <header class="console-header">
      <h1>Benchmark console<span>.</span></h1>
      <div class="console-facts">
        <span><strong>{allCases.length}</strong> pinned cases</span>
        <span><strong>{loadedRevision ? runs.length : '—'}</strong> {loadedRevision ? 'recorded runs' : 'history on demand'}</span>
        <span>Inspect AI</span>
      </div>
    </header>
    <ConsoleStatus {connectionError} {historyError} {warnings} />
    {#if job?.status === 'running'}<LiveRun {job} {taskName} />{/if}
    <div class:single={activeView !== 'run'} class="workspace">
      <section class="run-panel" class:view-hidden={activeView !== 'run'} id="run" aria-labelledby="run-title">
        <div class="section-head"><div><h2 id="run-title">Set up a run<span>.</span></h2></div><b>{selectedCases.length} {selectedCases.length === 1 ? 'TASK' : 'TASKS'}</b></div>
        <SuitePicker {suites} bind:selection />
        <div class="field">
          <div class="field-head"><strong>Model source</strong><span>Choose where requests go</span></div>
          <div class="source-grid" role="group" aria-label="Model source">
            {#each SOURCES as option (option)}
              <button type="button" class:selected={source === option} aria-pressed={source === option} onclick={() => chooseSource(option)}>
                <span class="symbol" aria-hidden="true">{#if option === 'freetoken'}<Radio size={22}/>{:else if option === 'openrouter'}<ArrowUpRight size={22}/>{:else}<Network size={22}/>{/if}</span>
                <strong>{SOURCE_LABELS[option]}</strong><small>{SOURCE_HINTS[option]}</small>
              </button>
            {/each}
          </div>
        </div>
        {#if source === 'compatible'}
          <div class="field">
            <div class="field-head"><label for="endpoint">OpenAI-compatible endpoint</label><span>Private HTTP /v1</span></div>
            <div class="input-action"><input id="endpoint" type="url" bind:value={baseUrl} spellcheck="false" /><button type="button" onclick={loadModels}>Connect</button></div>
          </div>
        {/if}
        <div class="field">
          <div class="field-head"><label for="model-search">Model</label><span>{loading ? 'Checking catalog…' : `${catalog.length} shown`}</span></div>
          <div class="search"><Search size={17} aria-hidden="true"/><input id="model-search" placeholder={source === 'openrouter' ? 'Search OpenRouter models' : 'Filter served models'} bind:value={query} oninput={search} autocomplete="off" /></div>
          {#if catalogError}
            <div class="message error" role="alert">{catalogError} <button type="button" onclick={loadModels}>Retry</button></div>
          {:else if loading}
            <div class="catalog-empty">Checking available models…</div>
          {:else if !catalog.length}
            <div class="catalog-empty">{source === 'compatible' ? 'Enter an endpoint and connect to list its models.' : 'No matching models. Try another search.'}</div>
          {:else}
            <div class="model-list" role="radiogroup" aria-label="Available models">
              {#each catalog as option (option.id)}
                <label class:chosen={selectedModel === option.id}>
                  <input type="radio" name="model" value={option.id} bind:group={selectedModel} /><i></i>
                  <span><strong>{option.name}</strong><small>{option.id}</small></span>
                  {#if option.contextLength}<em>{Math.round(option.contextLength / 1000)}K CTX</em>{/if}
                </label>
              {/each}
            </div>
          {/if}
        </div>
        {#if variantOptions.length > 1}<PromptPicker options={variantOptions} bind:variants />{/if}
        {#if source === 'openrouter' && (paidRun || !data.sources.openrouter.configured)}
          <PaidGuard {maxCalls} configured={data.sources.openrouter.configured} paid={paidRun} bind:capUsd bind:capConfirmed />
        {/if}
        <div class="run-actions">
          <div class="call-count"><strong>{maxCalls}</strong><small>MAX MODEL<br />CALLS</small></div>
          <button class="run-button" type="button" disabled={!canRun} onclick={run}>
            <span>{job?.status === 'running' ? 'RUN IN PROGRESS' : selection.includes(SELECT_ALL) ? 'RUN EVERYTHING' : 'RUN BENCHMARK'}</span><ArrowRight size={19} aria-hidden="true"/>
          </button>
        </div>
        {#if runError}<div class="message error" role="alert">{runError}</div>{/if}
        {#if job}<JobStatus {job} resultsCount={jobResults.length} passedCount={jobPassed} {taskName} refresh={() => polling?.wake()} />{/if}
      </section>
      <section class="report-panel" id="report" aria-labelledby="report-title">
        <div class:hidden-view={activeView === 'activity'}>
          <Scorecard {runs} cases={allCases} loaded={Boolean(loadedRevision)} onDemand={activeView === 'run'} failed={Boolean(historyError)} />
        </div>
        <div class="activity" class:hidden-view={activeView !== 'activity'} id="activity"><ActivityLog {runs} {taskName} /></div>
      </section>
    </div>
    <footer><span>mattbench / personal evaluation lab</span><span>Fixtures and scores stay pinned. Raw traces stay local.</span></footer>
  </main>
</div>
