/** Model sources; mirrors SOURCES in scripts/run_inspect_settings.py. */
export const SOURCES = ['freetoken', 'openrouter', 'compatible'] as const;
export type Source = (typeof SOURCES)[number];
export function isSource(value: unknown): value is Source { return SOURCES.includes(value as Source); }
/** Selection token that runs every registered suite. */
export const SELECT_ALL = 'all';
export type ModelOption = { id: string; name: string; contextLength?: number; promptPrice?: string; completionPrice?: string };
export type BenchmarkCase = { id: string; name: string; suite: string; maxModelCalls: number };
/** A registered benchmark suite, described by scripts/console_bridge.py from suites/. */
export type Suite = { id: string; label: string; description: string; variants: string[]; isolatedCases: boolean; cases: BenchmarkCase[] };
export type RunTiming = { setup_seconds?: number; evaluation_seconds?: number; teardown_seconds?: number; total_wall_seconds?: number };
export type Billing = { complete: boolean; cost_usd: number | null; partial_cost_usd: number | null; generation_attempts?: number; unknown_attempts?: number; lookup_failures?: number };
export type Row = {
  task: string; run_id: string; launcher_run_id?: string | null; sample_id: string; category?: string;
  prompt_variant: string; status: string; model: string; concrete_response_model?: string | null;
  routed_models?: string[]; providers?: string[]; passed: boolean | null; truncated?: boolean; billing?: Billing | null;
  score_explanation?: string | null; score_metadata?: Record<string, { state_correct?: boolean; trace_valid?: boolean; semantic_review_required?: boolean }>;
  latency_seconds?: number; model_calls?: number; tool_calls?: number;
  usage?: Record<string, { total_tokens?: number; total_cost?: number | null }>;
  started_at?: string; inference?: { temperature?: number; max_tokens?: number; max_retries?: number; timeout?: number };
  inspect_version?: string | null; task_version?: string | number; fixture?: string; log_file?: string; run_timing?: RunTiming | null;
};
/** One child process of a run (a whole suite, or one isolated case); never shown as a count. */
export type EntryResult = { entryId: string; status: 'complete' | 'failed'; passed?: boolean | null; modelCalls?: number; message?: string | null };
export const CASE_STATES = ['queued', 'running', 'pass', 'fail', 'unscored', 'error', 'not_run'] as const;
export type CaseState = (typeof CASE_STATES)[number];
/** Live state of one case under one prompt variant, from scripts/benchmark-worker.py --status. */
export type JobCase = { id: string; suite: string; variant: string; state: CaseState; truncated?: boolean; calls?: number; explanation?: string | null };
export type Job = {
  id: string; status: 'running' | 'complete' | 'failed' | 'interrupted'; source: Source; model: string;
  variants: string[]; selection: string[]; startedAt: string; updatedAt: string; finishedAt?: string; pid?: number | null;
  phase: 'validating' | 'preparing' | 'running' | 'billing' | 'exporting' | 'complete' | 'failed' | 'interrupted';
  currentEntryId?: string | null; completedEntries: EntryResult[]; totalEntries: number; cases: JobCase[]; message: string; error?: string;
};
export type RunInput = { source: Source; model: string; variants: string[]; selection: string[]; baseUrl?: string; maxCalls: number; capUsd?: number; capConfirmed?: boolean };
export type History = { revision: string; rows: Row[]; warnings: string[] };
export type Overview = { job: Job | null; revision: string };

export function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label} must be an object.`);
  return value as Record<string, unknown>;
}
function strings(value: Record<string, unknown>, fields: string[], label: string) {
  for (const key of fields) if (typeof value[key] !== 'string') throw new Error(`${label}.${key} must be a string.`);
}
function stringList(value: unknown): value is string[] { return Array.isArray(value) && value.every((entry) => typeof entry === 'string'); }
function nonnegative(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value) && value >= 0; }
export function parseJob(value: unknown): Job | null {
  if (value === null) return null;
  const job = object(value, 'Job');
  strings(job, ['id', 'source', 'model', 'startedAt', 'updatedAt', 'message'], 'Job');
  if (!/^\d{14,20}$/.test(String(job.id)) || !isSource(job.source) || !stringList(job.variants) || !stringList(job.selection) ||
      !['running', 'complete', 'failed', 'interrupted'].includes(String(job.status)) ||
      !['validating', 'preparing', 'running', 'billing', 'exporting', 'complete', 'failed', 'interrupted'].includes(String(job.phase)) ||
      !Number.isInteger(job.totalEntries) || !Array.isArray(job.completedEntries) || !Array.isArray(job.cases) ||
      (job.pid != null && (!Number.isInteger(job.pid) || Number(job.pid) <= 0))) throw new Error('Invalid persisted job contract.');
  for (const entry of job.cases) {
    const item = object(entry, 'Job case');
    strings(item, ['id', 'suite', 'variant'], 'Job case');
    if (!CASE_STATES.includes(item.state as CaseState) || (item.calls != null && !nonnegative(item.calls))) throw new Error('Invalid job case contract.');
  }
  for (const entry of job.completedEntries) {
    const result = object(entry, 'Entry result');
    if (typeof result.entryId !== 'string' || !['complete', 'failed'].includes(String(result.status)) ||
        (result.passed != null && typeof result.passed !== 'boolean') ||
        (result.modelCalls != null && !nonnegative(result.modelCalls))) throw new Error('Invalid entry result contract.');
  }
  return job as unknown as Job;
}
export function parseSuite(value: unknown): Suite {
  const suite = object(value, 'Suite');
  strings(suite, ['id', 'label', 'description'], 'Suite');
  if (!stringList(suite.variants) || !suite.variants.length || typeof suite.isolatedCases !== 'boolean' || !Array.isArray(suite.cases)) {
    throw new Error(`Suite ${suite.id} has an invalid contract.`);
  }
  const cases = suite.cases.map((entry) => {
    const item = object(entry, 'Case');
    strings(item, ['id', 'name'], 'Case');
    if (!Number.isInteger(item.maxModelCalls) || Number(item.maxModelCalls) < 1) throw new Error('Invalid case call ceiling.');
    return { id: item.id, name: item.name, maxModelCalls: item.maxModelCalls, suite: suite.id } as BenchmarkCase;
  });
  return { ...(suite as unknown as Suite), cases };
}
export function parseRow(value: unknown): Row {
  const row = object(value, 'Summary row');
  strings(row, ['task', 'run_id', 'sample_id', 'prompt_variant', 'status', 'model'], 'Summary row');
  for (const key of ['started_at', 'fixture', 'log_file', 'concrete_response_model', 'inspect_version', 'score_explanation']) {
    if (row[key] != null && typeof row[key] !== 'string') throw new Error(`Summary row.${key} must be a string.`);
  }
  for (const key of ['routed_models', 'providers']) {
    if (row[key] != null && (!Array.isArray(row[key]) || row[key].some((value) => typeof value !== 'string'))) throw new Error(`Summary row.${key} must contain strings.`);
  }
  if (row.passed !== null && typeof row.passed !== 'boolean') throw new Error('Summary row.passed must be boolean or null.');
  for (const key of ['model_calls', 'tool_calls', 'latency_seconds']) if (row[key] != null && !nonnegative(row[key])) throw new Error(`Summary row.${key} must be nonnegative.`);
  if (row.usage != null) {
    for (const value of Object.values(object(row.usage, 'Usage'))) {
      const use = object(value, 'Model usage');
      for (const key of ['total_tokens', 'total_cost']) if (use[key] != null && !nonnegative(use[key])) throw new Error(`Usage.${key} must be nonnegative.`);
    }
  }
  if (row.billing != null) {
    const billing = object(row.billing, 'Billing');
    if (typeof billing.complete !== 'boolean' ||
        (billing.complete ? !nonnegative(billing.cost_usd) || billing.partial_cost_usd !== null : billing.cost_usd !== null || billing.partial_cost_usd != null && !nonnegative(billing.partial_cost_usd))) {
      throw new Error('Invalid billing completeness contract.');
    }
    for (const key of ['generation_attempts', 'unknown_attempts', 'lookup_failures']) {
      if (billing[key] != null && (!Number.isInteger(billing[key]) || !nonnegative(billing[key]))) throw new Error(`Billing.${key} must be a nonnegative integer.`);
    }
  }
  return row as unknown as Row;
}
export function parseOverview(value: unknown): Overview {
  const overview = object(value, 'Overview');
  if (typeof overview.revision !== 'string') throw new Error('Overview revision is missing.');
  return { revision: overview.revision, job: parseJob(overview.job) };
}
export function parseHistory(value: unknown): History {
  const history = object(value, 'History');
  if (typeof history.revision !== 'string' || !Array.isArray(history.rows) ||
      !Array.isArray(history.warnings) || history.warnings.some((warning) => typeof warning !== 'string')) throw new Error('Invalid history response.');
  return { revision: history.revision, rows: history.rows.map(parseRow), warnings: history.warnings as string[] };
}
