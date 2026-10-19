<script lang="ts">
  import type { CaseResult, Job } from './contracts';
  import { caseResultLabel } from './format';

  let { job, taskName }: { job: Job; taskName: (id: string) => string } = $props();
  let total = $derived(job.totalCases || 1);
  let done = $derived(job.completedCount || 0);
  let phase = $derived(job.phase.replaceAll('_', ' '));
  function label(result: CaseResult) {
    return `${taskName(result.caseId)}: ${caseResultLabel(result)}${result.modelCalls !== undefined ? ` · ${result.modelCalls} calls` : ''}`;
  }
</script>

<div class="run-live" role="status" aria-live="polite">
  <span class="run-live-spinner" aria-hidden="true"></span>
  <div class="run-live-copy">
    <strong>{job.currentCaseId ? taskName(job.currentCaseId) : 'Preparing run'}</strong>
    <span>{job.message || `Run ${phase}`} · {done} of {total} cases finished</span>
  </div>
  <strong class="run-live-fraction">{done}/{total}</strong>
  <span class="run-live-track" role="progressbar" aria-label="Completed benchmark cases" aria-valuemin="0" aria-valuemax={total} aria-valuenow={done}>
    <i style:transform={`scaleX(${done / total})`}></i>
  </span>
  {#if job.completedCases.length}
    <div class="run-live-cases">{#each job.completedCases as result (result.caseId)}<span>{label(result)}</span>{/each}</div>
  {/if}
</div>
