import type { Row } from './contracts';

/** `launched`: started by the console worker; ad hoc pilot logs have no launcher run ID. */
export type RecordedRun = { key: string; rows: Row[]; model: string; runId: string; startedAt: string; pass: number; scored: number; unscored: number; prompts: string; launched: boolean };
export type MatrixRun = { key: string; runId: string; model: string; prompt: string; cases: Record<string, Row>; pass: number; scored: number; time: number; setup: number; cleanup: number; calls: number | null; tokens: number; cost: number | null; providers: string[]; routedModels: string[]; sample: Row };

export function tokens(row: Row): number {
  return Object.values(row.usage || {}).reduce((total, use) => total + (use.total_tokens || 0), 0);
}
export function cost(row: Row): number | null {
  if (row.model.startsWith('openai-api/openrouter/')) return row.billing?.complete === true ? row.billing.cost_usd : null;
  const values = Object.values(row.usage || {}).map((use) => use.total_cost);
  return values.length && values.every((value) => typeof value === 'number') ? values.reduce<number>((sum, value) => sum + Number(value), 0) : null;
}
export function groupRuns(rows: Row[]): RecordedRun[] {
  const groups: Record<string, Row[]> = Object.create(null);
  for (const row of rows) {
    if (row.model.startsWith('mockllm/')) continue;
    const key = JSON.stringify([row.launcher_run_id || row.run_id, row.model]);
    (groups[key] ??= []).push(row);
  }
  return Object.entries(groups).map(([key, group]) => {
    const ordered = [...group].sort((a, b) => (a.started_at || '').localeCompare(b.started_at || ''));
    return {
      key, rows: ordered, model: ordered[0].model, runId: ordered[0].launcher_run_id || ordered[0].run_id,
      startedAt: ordered[0].started_at || '', pass: ordered.filter((row) => row.passed === true).length,
      scored: ordered.filter((row) => row.passed !== null).length, unscored: ordered.filter((row) => row.passed === null).length,
      prompts: [...new Set(ordered.map((row) => row.prompt_variant))].join(' + '),
      launched: Boolean(ordered[0].launcher_run_id)
    };
  }).sort((a, b) => b.startedAt.localeCompare(a.startedAt));
}
export function matrixRuns(rows: Row[]): MatrixRun[] {
  const groups: Record<string, Row[]> = Object.create(null);
  for (const row of rows) (groups[row.prompt_variant] ??= []).push(row);
  return Object.values(groups).map((group) => {
    const first = group[0];
    const runId = first.launcher_run_id || first.run_id;
    const costs = group.map(cost);
    return {
      key: `${first.model}|${first.prompt_variant}|${runId}`, runId, model: first.model, prompt: first.prompt_variant,
      cases: Object.fromEntries(group.map((row) => [row.sample_id, row])),
      pass: group.filter((row) => row.passed === true).length, scored: group.filter((row) => row.passed !== null).length,
      time: group.reduce((sum, row) => sum + (row.latency_seconds || 0), 0),
      setup: group.reduce((sum, row) => sum + (row.run_timing?.setup_seconds || 0), 0),
      cleanup: group.reduce((sum, row) => sum + (row.run_timing?.teardown_seconds || 0), 0),
      calls: group.every((row) => row.model_calls !== undefined) ? group.reduce((sum, row) => sum + (row.model_calls || 0), 0) : null,
      tokens: group.reduce((sum, row) => sum + tokens(row), 0),
      cost: costs.every((value) => value !== null) ? costs.reduce<number>((sum, value) => sum + (value || 0), 0) : null,
      providers: [...new Set(group.flatMap((row) => row.providers || []))],
      routedModels: [...new Set(group.flatMap((row) => row.routed_models || []))], sample: first
    };
  }).sort((a, b) => a.prompt.localeCompare(b.prompt));
}
