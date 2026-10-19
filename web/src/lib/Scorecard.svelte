<script lang="ts">
  import { Info } from '@lucide/svelte';
  import type { BenchmarkCase, Suite } from './contracts';
  import { matrixRuns, type RecordedRun } from './results';
  import { coverageNamer, formatNumber, formatSeconds, shortModelName, SOURCE_LABELS, sourceOf } from './format';
  import RunPicker from './RunPicker.svelte';
  import RunDetail from './RunDetail.svelte';

  /** `onDemand`: history is not fetched until the Results view opens. */
  let { runs, suites, loaded, failed }: { runs: RecordedRun[]; suites: Suite[]; loaded: boolean; failed: boolean } = $props();
  let cases = $derived<BenchmarkCase[]>(suites.flatMap((suite) => suite.cases));
  let coverage = $derived(coverageNamer(suites));
  let includePilots = $state(false);
  type Filter = 'all' | 'local' | 'hosted';
  const filters: { id: Filter; label: string }[] = [{ id: 'all', label: 'All' }, { id: 'local', label: 'Local' }, { id: 'hosted', label: 'Hosted' }];
  let filter = $state<Filter>('all');
  let selectedRunKey = $state('');
  let detailKey = $state('');

  let caseIds = $derived(new Set(cases.map((entry) => entry.id)));
  function matchesFilter(run: RecordedRun) {
    const hosted = sourceOf(run.model) === 'openrouter';
    return filter === 'all' || (filter === 'hosted') === hosted;
  }
  let visibleRuns = $derived(runs.filter((run) => (includePilots || run.launched) && run.rows.some((row) => caseIds.has(row.sample_id)) && matchesFilter(run)));
  let selectedRun = $derived(visibleRuns.find((run) => run.key === selectedRunKey) || visibleRuns[0]);
  let matrix = $derived(matrixRuns((selectedRun?.rows || []).filter((row) => caseIds.has(row.sample_id))));
  let detail = $derived(matrix.find((entry) => entry.key === detailKey));
</script>

<div class="section-head"><div><h2 id="report-title">The scorecard<span>.</span></h2><p>All pinned fixture cases. Missing outcomes stay marked NOT RUN.</p></div><b>LIVE DATA</b></div>
<div class="note"><Info size={17} aria-hidden="true"/> These pilot cases screen the workflow. A few tasks cannot establish broad model superiority.</div>
<div class="report-toolbar">
  <strong>RUN RESULTS</strong>
  <div role="group" aria-label="Filter results">
    {#each filters as option (option.id)}<button class:selected={filter === option.id} onclick={() => filter = option.id}>{option.label}</button>{/each}
  </div>
</div>
<label class="pilot-toggle"><input type="checkbox" bind:checked={includePilots} /> Include pilot runs made outside the console</label>
{#if selectedRun}
  <RunPicker id="report-run" runs={visibleRuns} selected={selectedRun} {coverage} onselect={(key) => { selectedRunKey = key; detailKey = ''; }} />
{/if}
{#if matrix.length}
  <div class="matrix-wrap"><table>
    <thead><tr><th scope="col">Model / prompt</th><th scope="col">Score</th><th scope="col">Calls</th><th scope="col">Model time</th><th scope="col">Setup</th><th scope="col">Cleanup</th><th scope="col">Tokens</th><th scope="col">Cost</th></tr></thead>
    <tbody>
      {#each matrix as entry (entry.key)}
        <tr>
          <th scope="row">
            <strong>{shortModelName(entry.model)}</strong>
            <small>{SOURCE_LABELS[sourceOf(entry.model)]} · {entry.prompt} prompt · {entry.runId}</small>
            <button class="detail-link" type="button" aria-expanded={detailKey === entry.key} onclick={() => detailKey = detailKey === entry.key ? '' : entry.key}>Run details</button>
          </th>
          <td><div class="score"><strong>{entry.scored ? `${entry.pass}/${entry.scored}` : '—'}</strong><span><i style:width={`${entry.scored ? entry.pass / entry.scored * 100 : 0}%`}></i></span></div></td>
          <td class="numeric">{entry.calls === null ? '—' : entry.calls}</td>
          <td class="numeric">{formatSeconds(entry.time)}</td>
          <td class="numeric">{entry.setup ? formatSeconds(entry.setup) : '—'}</td>
          <td class="numeric">{entry.cleanup ? formatSeconds(entry.cleanup) : '—'}</td>
          <td class="numeric">{formatNumber(entry.tokens)}</td>
          <td class="numeric">{entry.cost === null ? '—' : `$${entry.cost.toFixed(6)}`}</td>
        </tr>
      {/each}
    </tbody>
  </table></div>
{:else if !loaded}
  <div class="empty"><strong>{failed ? 'Results could not be loaded.' : 'Loading result history…'}</strong></div>
{:else}
  <div class="empty"><div aria-hidden="true">×</div><strong>No runs in this view yet.</strong><p>Choose another source filter, or run a pinned benchmark to see its task results here.</p></div>
{/if}
{#if detail}<RunDetail run={detail} {cases} onclose={() => detailKey = ''} />{/if}

<style>
  .pilot-toggle { display: flex; align-items: center; gap: 7px; margin: -4px 0 14px; font-size: 11px; color: #596b5c; }
  .pilot-toggle input { accent-color: #366e37; }
</style>
