<script lang="ts">
  import type { RecordedRun } from './results';
  import { formatRunTime, modelName } from './format';

  let { id, runs, selected, onselect, coverage, showRunId = false }: {
    id: string; runs: RecordedRun[]; selected: RecordedRun; onselect: (key: string) => void;
    coverage: (sampleIds: string[]) => string; showRunId?: boolean;
  } = $props();
  function covered(run: RecordedRun) { return coverage(run.rows.map((row) => row.sample_id)); }
  function score(run: RecordedRun) { return run.scored ? `${run.pass} of ${run.scored} passed` : 'No scored tasks'; }
</script>

<div class="run-picker">
  <label for={id}>Choose a run</label>
  <select {id} value={selected.key} onchange={(event) => onselect(event.currentTarget.value)}>
    {#each runs as run (run.key)}<option value={run.key}>{formatRunTime(run.startedAt)} · {modelName(run.model)} · {covered(run)} · {score(run)}</option>{/each}
  </select>
  <div class="run-picker-summary">
    <strong>{modelName(selected.model)}</strong>
    <span>{formatRunTime(selected.startedAt)} · {covered(selected)} · {selected.prompts} prompt · {score(selected)}{selected.unscored ? ` · ${selected.unscored} unscored` : ''}</span>
    {#if showRunId}<small>Run {selected.runId} · {selected.rows.length} task {selected.rows.length === 1 ? 'record' : 'records'}</small>{/if}
  </div>
</div>
