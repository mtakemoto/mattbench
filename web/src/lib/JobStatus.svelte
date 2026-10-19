<script lang="ts">
  import type { Job } from './contracts';
  let { job, resultsCount, passedCount, taskName, refresh }: {
    job: Job; resultsCount: number; passedCount: number;
    taskName: (id: string) => string; refresh: () => void;
  } = $props();
  let phase = $derived(job.phase.replaceAll('_', ' '));
  let progress = $derived(job.totalCases ? Math.round(job.completedCount / job.totalCases * 100) : 0);
</script>

<div class:working={job.status === 'running'} class="job" role="status" aria-live="polite">
  <i></i>
  <span>
    <strong>
      {job.status === 'running' ? `Run ${phase}` : job.status === 'complete' ? resultsCount ? `Run finished · ${passedCount}/${resultsCount} passed` : 'Run finished' : job.status === 'interrupted' ? 'Run interrupted' : 'Run stopped'}
    </strong>
    <small>{job.currentCaseId ? `${taskName(job.currentCaseId)} · ` : ''}{job.message || job.error}</small>
    {#if job.totalCases}
      <span class="progress-track" role="progressbar" aria-label="Benchmark progress" aria-valuemin="0" aria-valuemax={job.totalCases} aria-valuenow={job.completedCount}>
        <i style:transform={`scaleX(${progress / 100})`}></i>
      </span>
    {/if}
    {#if job.completedCases.length}
      <span class="case-status-list">
        {#each job.completedCases as done (done.caseId)}
          <span class:failed={done.status === 'failed' || done.passed === false}>
            {done.status === 'failed' ? 'ERROR' : done.passed === true ? 'PASS' : done.passed === false ? 'FAIL' : 'DONE'} · {taskName(done.caseId)}{done.modelCalls !== undefined ? ` · ${done.modelCalls} calls` : ''}
          </span>
        {/each}
      </span>
    {/if}
  </span>
  {#if job.status !== 'running'}<button type="button" onclick={refresh}>Refresh</button>{/if}
</div>
