<script lang="ts">
  import type { BenchmarkCase, Row } from './contracts';
  import type { MatrixRun } from './results';
  import { formatSeconds, modelName, outcomeLabel, plural, SOURCE_LABELS, sourceOf } from './format';
  import BillingStatus from './BillingStatus.svelte';

  let { run, cases, onclose }: { run: MatrixRun; cases: BenchmarkCase[]; onclose: () => void } = $props();
  let sample = $derived(run.sample);

  function notes(row: Row): string {
    const scorers = Object.values(row.score_metadata ?? {});
    return [
      row.model_calls == null ? '— calls' : plural(row.model_calls, 'call'), formatSeconds(row.latency_seconds),
      row.truncated ? 'Output truncated at the token limit' : '',
      scorers.some((meta) => meta.state_correct === true) ? 'Final state reached' : '',
      scorers.some((meta) => meta.trace_valid === false) ? 'Tool sequence failed' : '',
      row.score_explanation ?? ''
    ].filter(Boolean).join(' · ');
  }
</script>

<div class="run-detail" aria-label="Selected run details">
  <div class="detail-head"><h3>Run details</h3><button type="button" onclick={onclose}>Close</button></div>
  <div class="detail-cases">
    <strong>Task outcomes</strong>
    {#each cases as benchmark (benchmark.id)}
      {@const result = run.cases[benchmark.id]}
      {#if result}
        <div class:failed={result.passed === false}>
          <span>{benchmark.name}</span>
          <b class:pass={result.passed === true} class:miss={result.passed === false}>{outcomeLabel(result.passed)}</b>
          <small>{notes(result)}</small>
        </div>
      {/if}
    {/each}
  </div>
  <dl>
    <div><dt>Exact model ID</dt><dd>{modelName(run.model)}</dd></div>
    <div><dt>Source</dt><dd>{SOURCE_LABELS[sourceOf(run.model)]}</dd></div>
    <div><dt>Prompt</dt><dd>{run.prompt}</dd></div>
    <div><dt>Run ID</dt><dd>{run.runId}</dd></div>
    <div><dt>Routed model</dt><dd>{run.routedModels.join(', ') || sample.concrete_response_model || 'Not reported'}</dd></div>
    <div><dt>Providers</dt><dd>{run.providers.join(', ') || 'Not reported'}</dd></div>
    <div><dt>Started</dt><dd>{sample.started_at || 'Not reported'}</dd></div>
    <div><dt>Inference</dt><dd>Temperature {sample.inference?.temperature ?? '—'} · max {sample.inference?.max_tokens ?? '—'} tokens · {sample.inference?.max_retries ?? '—'} retries · {sample.inference?.timeout ?? '—'}s timeout</dd></div>
    <div><dt>Fixture / version</dt><dd>{sample.fixture || '—'} · task v{sample.task_version || '—'} · Inspect {sample.inspect_version || '—'}</dd></div>
    <div><dt>Inspect log</dt><dd>{sample.log_file || 'Not reported'}</dd></div>
    {#if sample.run_timing}
      <div><dt>Container setup / cleanup</dt><dd>{formatSeconds(sample.run_timing.setup_seconds)} / {formatSeconds(sample.run_timing.teardown_seconds)}</dd></div>
      <div><dt>Evaluation / wall time</dt><dd>{formatSeconds(sample.run_timing.evaluation_seconds)} / {formatSeconds(sample.run_timing.total_wall_seconds)}</dd></div>
    {/if}
  </dl>
</div>
<BillingStatus rows={Object.values(run.cases)} />

<style>
  .failed { background: #f4d6cd; border-radius: 7px; padding-left: 10px !important; padding-right: 10px; border-top-color: #e3b3a5 !important; color: #5c1f14; }
  .failed small { color: #7a3326 !important; }
</style>
