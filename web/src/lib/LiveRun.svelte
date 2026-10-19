<script lang="ts">
  import { ChevronDown } from '@lucide/svelte';
  import CaseGrid from './CaseGrid.svelte';
  import type { Job } from './contracts';
  import type { RunProgress } from './progress';

  /** Sticky one-line run status for views without the live panel; expands into the case grid. */
  let { job, progress }: { job: Job; progress: RunProgress } = $props();
  const STORAGE_KEY = 'mattbench.liveRunExpanded';
  let expanded = $state(readExpanded());
  function readExpanded() {
    try { return localStorage.getItem(STORAGE_KEY) === 'true'; } catch { return false; }
  }
  function toggle() {
    expanded = !expanded;
    try { localStorage.setItem(STORAGE_KEY, String(expanded)); } catch { /* Preference only. */ }
  }
  let current = $derived(progress.current);
</script>

<div class="run-live" role="status" aria-live="polite">
  <span class="run-live-spinner" aria-hidden="true"></span>
  <div class="run-live-copy">
    <strong>{[`${progress.done} of ${progress.total} cases`, current && `${current.row.suite.label} ${current.row.done} of ${current.row.total}`].filter(Boolean).join(' · ')}</strong>
    <span>{current ? `${current.entry.name} · ${job.message}` : job.message}</span>
  </div>
  <span class="run-live-tally">{progress.passed} pass · {progress.failed} fail</span>
  <button class="run-live-toggle" type="button" aria-expanded={expanded} aria-label={expanded ? 'Hide case progress' : 'Show case progress'} onclick={toggle}>
    <ChevronDown size={18} aria-hidden="true" />
  </button>
  <span class="run-live-track" role="progressbar" aria-label="Finished cases" aria-valuemin="0" aria-valuemax={progress.total} aria-valuenow={progress.done}>
    <i style:transform={`scaleX(${progress.total ? progress.done / progress.total : 0})`}></i>
  </span>
  {#if expanded}<div class="run-live-grid"><CaseGrid {progress} tone="dark" /></div>{/if}
</div>

<style>
  .run-live { grid-template-columns: 20px minmax(0, 1fr) auto auto; }
  .run-live-tally { font: 700 10px 'JetBrains Mono Variable', monospace; color: #b3c2b2; white-space: nowrap; }
  .run-live-toggle { border: 1px solid #596b5c; background: #2c382e; color: #d8ee6b; border-radius: 7px; width: 30px; height: 30px; display: grid; place-items: center; }
  .run-live-toggle:hover { background: #40543d; }
  .run-live-toggle :global(svg) { transition: transform .2s cubic-bezier(.16, 1, .3, 1); }
  .run-live-toggle[aria-expanded='true'] :global(svg) { transform: rotate(180deg); }
  .run-live-track { grid-column: 2 / 5; }
  .run-live-grid { grid-column: 2 / 5; max-height: 45vh; overflow: auto; }
  @media (max-width: 620px) { .run-live-tally { display: none; } .run-live { grid-template-columns: 20px minmax(0, 1fr) auto; } .run-live-track, .run-live-grid { grid-column: 1 / -1; } }
</style>
