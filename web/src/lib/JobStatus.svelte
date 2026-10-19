<script lang="ts">
  import { Square } from '@lucide/svelte';
  import type { Job } from './contracts';
  import type { RunProgress } from './progress';

  /** Compact job card under the Run button: what is happening, case progress, and Cancel. */
  let { job, progress, oncancel, cancelling }: {
    job: Job; progress: RunProgress; oncancel: () => void; cancelling: boolean;
  } = $props();
  let running = $derived(job.status === 'running');
  let headline = $derived(running ? `Running · ${progress.done} of ${progress.total} cases`
    : job.status === 'complete' ? `Run finished · ${progress.passed} of ${progress.total} passed`
    : job.status === 'interrupted' ? `Run stopped · ${progress.done} of ${progress.total} cases finished`
    : 'Run failed');
</script>

<div class:working={running} class="job" role="status" aria-live="polite">
  <i></i>
  <span>
    <strong>{headline}</strong>
    <small>{job.message || job.error}</small>
    {#if progress.total}
      <span class="progress-track" role="progressbar" aria-label="Finished cases" aria-valuemin="0" aria-valuemax={progress.total} aria-valuenow={progress.done}>
        <i style:transform={`scaleX(${progress.done / progress.total})`}></i>
      </span>
    {/if}
  </span>
  {#if running}
    <button class="cancel" type="button" onclick={oncancel} disabled={cancelling || job.phase === 'billing' || job.phase === 'exporting'}>
      <Square size={11} aria-hidden="true" />{cancelling ? 'Cancelling…' : 'Cancel run'}
    </button>
  {/if}
</div>

<style>
  .cancel { display: inline-flex; align-items: center; gap: 6px; border: 1px solid #ba553e; background: #51312d; color: #ffc1ad; border-radius: 7px; padding: 7px 10px; font-size: 11px; font-weight: 800; white-space: nowrap; text-decoration: none; }
  .cancel:hover:not(:disabled) { background: #6a3a33; }
  .cancel:disabled { opacity: .55; }
</style>
