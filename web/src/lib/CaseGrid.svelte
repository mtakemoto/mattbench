<script lang="ts">
  import CaseMark from './CaseMark.svelte';
  import type { RunProgress } from './progress';

  /** Category rows with one mark per case; `tone` matches the dark strip or the light report panel. */
  let { progress, tone }: { progress: RunProgress; tone: 'dark' | 'light' } = $props();
  function tally(row: RunProgress['rows'][number]) {
    return [row.passed && `${row.passed} pass`, row.failed && `${row.failed} fail`, row.errors && `${row.errors} error`,
      row.notRun && `${row.notRun} not run`]
      .filter(Boolean).join(' · ');
  }
</script>

<div class="grid {tone}">
  {#each progress.rows as row (row.suite.id)}
    <div class="row" class:has-failure={row.failed || row.errors}>
      <strong>{row.suite.label}</strong>
      <span class="marks">{#each row.cases as entry (entry.key)}<CaseMark {entry} />{/each}</span>
      <span class="count">{row.done}/{row.total}</span>
      <span class="tally">{tally(row)}</span>
      {#if progress.current?.row === row}<small class="now">Now: {progress.current.entry.name}</small>{/if}
    </div>
  {/each}
  {#each progress.warnings as warning (warning)}<p class="warning" role="status">{warning}</p>{/each}
</div>

<style>
  .grid { display: grid; gap: 2px; font-size: 11px; }
  .dark { --mark-muted: #b3c2b2; --mark-accent: #d8ee6b; --mark-pass: #d8ee6b; --mark-pass-surface: #40543d; --mark-miss: #ffc1ad; --mark-miss-surface: #51312d; --row-text: #f4f0e6; --row-muted: #b3c2b2; --row-line: #343d35; }
  .light { --mark-muted: #596b5c; --mark-accent: #366e37; --mark-pass: #366e37; --mark-pass-surface: #dce6c5; --mark-miss: #8e2f1f; --mark-miss-surface: #f4d6cd; --row-text: #18231a; --row-muted: #596b5c; --row-line: #d0d5c4; }
  .row { display: grid; grid-template-columns: minmax(110px, 160px) minmax(0, 1fr) auto; align-items: center; gap: 4px 14px; padding: 8px 0; border-bottom: 1px solid var(--row-line); color: var(--row-text); }
  .row:last-of-type { border-bottom: 0; }
  .row strong { font-weight: 800; }
  .marks { display: flex; flex-wrap: wrap; gap: 3px; }
  .count { font: 700 10px 'JetBrains Mono Variable', monospace; font-variant-numeric: tabular-nums; color: var(--row-muted); text-align: right; }
  .tally { grid-column: 2 / 4; font: 700 9px 'JetBrains Mono Variable', monospace; color: var(--row-muted); }
  .tally:empty { display: none; }
  .now { grid-column: 2 / 4; color: var(--row-muted); }
  .warning { margin: 8px 0 0; padding: 9px 11px; border-radius: 7px; background: var(--mark-miss-surface); color: var(--mark-miss); font-weight: 700; line-height: 1.4; }
  @media (max-width: 620px) { .row { grid-template-columns: minmax(0, 1fr) auto; } .marks { grid-column: 1 / -1; grid-row: 2; } .tally, .now { grid-column: 1 / -1; } }
</style>
