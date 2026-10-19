<script lang="ts">
  import type { RecordedRun } from './results';
  import { tokens } from './results';
  import { formatNumber, formatRunTime, formatSeconds, outcomeLabel, plural } from './format';
  import RunPicker from './RunPicker.svelte';

  let { runs, taskName }: { runs: RecordedRun[]; taskName: (id: string) => string } = $props();
  let selectedKey = $state('');
  let selected = $derived(runs.find((run) => run.key === selectedKey) || runs[0]);
</script>

<div class="activity-head"><h3>Activity</h3><span>{plural(runs.length, 'RUN').toUpperCase()}</span></div>
{#if selected}
  <RunPicker id="activity-run" {runs} {selected} onselect={(key) => selectedKey = key} showRunId />
  {#each selected.rows as row (`${row.run_id}-${row.sample_id}-${row.prompt_variant}`)}
    <div class="activity-row">
      <i class:good={row.passed === true} class:bad={row.passed === false}></i>
      <div>
        <strong>{taskName(row.sample_id)}</strong>
        <small>{row.prompt_variant} prompt · {formatRunTime(row.started_at || '')}{row.truncated ? ' · Output truncated' : ''}{row.score_explanation ? ` · ${row.score_explanation}` : ''}</small>
      </div>
      <aside>
        <strong>{outcomeLabel(row.passed)}</strong>
        <small>{formatSeconds(row.latency_seconds)} · {row.model_calls ?? '—'} calls · {formatNumber(tokens(row))} tok</small>
      </aside>
    </div>
  {/each}
{:else}
  <p class="activity-empty">Run a benchmark to build an activity trail.</p>
{/if}
