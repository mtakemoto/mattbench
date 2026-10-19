<script lang="ts">
  import CaseGrid from './CaseGrid.svelte';
  import type { Job, Row } from './contracts';
  import { formatNumber, formatRunTime, formatSeconds, plural } from './format';
  import { isFailure, STATE_LABELS, type RunProgress } from './progress';
  import { matrixRuns } from './results';

  /** The Run view's right side: the active or most recent job, live while it runs and summarised after. */
  let { job, progress, rows }: { job: Job | null; progress: RunProgress | null; rows: Row[] } = $props();
  let summary = $derived(job && job.status !== 'running'
    ? matrixRuns(rows.filter((row) => row.launcher_run_id === job.id)) : []);
  let finished = $derived(progress ? progress.rows.flatMap((row) => row.cases.filter((entry) => !['queued', 'running', 'not_run'].includes(entry.state))
    .map((entry) => ({ ...entry, category: row.suite.label }))) : []);
</script>

<div class="section-head">
  <div>
    <h2 id="current-title">{job?.status === 'running' ? 'Current run' : 'Latest run'}<span>.</span></h2>
    {#if job}<p>{job.model} · started {formatRunTime(job.startedAt)}</p>{/if}
  </div>
  {#if progress}<b>{progress.done}/{progress.total} CASES</b>{/if}
</div>

{#if !job || !progress}
  <div class="empty"><strong>No run yet.</strong><p>Choose categories and a model, then run. Progress appears here case by case.</p></div>
{:else}
  <div class="panel"><CaseGrid {progress} tone="light" /></div>

  {#each summary as entry (entry.key)}
    <dl class="totals">
      <div><dt>Score</dt><dd>{progress.passed}/{progress.done}</dd></div>
      <div><dt>Model calls</dt><dd>{progress.calls}</dd></div>
      <div><dt>Model time</dt><dd>{formatSeconds(entry.time)}</dd></div>
      <div><dt>Tokens</dt><dd>{formatNumber(entry.tokens)}</dd></div>
      <div><dt>Cost</dt><dd>{job.source !== 'openrouter' ? 'No hosted charge' : entry.cost === null ? 'Unknown' : `$${entry.cost.toFixed(6)}`}</dd></div>
    </dl>
  {/each}
  {#if summary.length}<p class="history-link"><a href="#report">Compare with earlier runs in Results</a></p>{/if}

  {#if finished.length}
    <h3>Case outcomes <small>{plural(finished.length, 'case')} finished{progress.notRun ? ` · ${progress.notRun} not run` : ''}</small></h3>
    <ol class="outcomes">
      {#each finished as entry (entry.key)}
        <li class:failed={isFailure(entry.state)} class:passed={entry.state === 'pass'}>
          <span><strong>{entry.name}</strong><small>{entry.category}</small></span>
          <b>{STATE_LABELS[entry.state].toUpperCase()}</b>
          <small class="why">{[entry.calls != null ? plural(entry.calls, 'call') : '', entry.truncated ? 'Cut off at the token limit' : '', entry.explanation ?? ''].filter(Boolean).join(' · ')}</small>
        </li>
      {/each}
    </ol>
  {/if}
{/if}

<style>
  .panel { border: 1px solid #d0d5c4; border-radius: 9px; background: #fbfaf2; padding: 6px 14px; }
  .totals { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin: 16px 0 0; padding: 14px; border: 1px solid #d0d5c4; border-radius: 9px; background: #fbfaf2; }
  .totals dt { font: 700 9px 'JetBrains Mono Variable', monospace; color: #596b5c; text-transform: uppercase; letter-spacing: .05em; }
  .totals dd { margin: 5px 0 0; font: 800 15px 'JetBrains Mono Variable', monospace; font-variant-numeric: tabular-nums; }
  .history-link { margin: 10px 0 0; font-size: 11px; }
  .history-link a { color: #366e37; font-weight: 800; text-underline-offset: 3px; }
  h3 { display: flex; align-items: baseline; justify-content: space-between; font: 800 18px 'Bricolage Grotesque Variable', sans-serif; letter-spacing: -.02em; margin: 26px 0 8px; }
  h3 small { font: 700 9px 'JetBrains Mono Variable', monospace; color: #596b5c; letter-spacing: .05em; }
  .outcomes { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
  .outcomes li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 12px; padding: 10px 12px; border-radius: 7px; background: #fbfaf2; border: 1px solid #d0d5c4; }
  .outcomes li.failed { background: #f4d6cd; border-color: #e3b3a5; color: #5c1f14; }
  .outcomes li span strong { display: block; font-size: 11px; }
  .outcomes li span small { display: block; font-size: 10px; color: #596b5c; margin-top: 2px; }
  .outcomes li.failed span small, .outcomes li.failed .why { color: #7a3326; }
  .outcomes b { font: 800 10px 'JetBrains Mono Variable', monospace; color: #596b5c; }
  .outcomes li.passed b { color: #366e37; }
  .outcomes li.failed b { color: #8e2f1f; }
  .why { grid-column: 1 / -1; font-size: 10px; color: #596b5c; line-height: 1.4; }
  .why:empty { display: none; }
  @media (max-width: 900px) { .totals { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
