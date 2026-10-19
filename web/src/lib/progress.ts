import type { CaseState, Job, JobCase, Suite } from './contracts';

/** A case is finished once it has an outcome, including an evaluator error; cancelled cases are never finished. */
const UNFINISHED: CaseState[] = ['queued', 'running', 'not_run'];
/** Cut-off answers in one category before the console warns that scores may measure the token limit. */
export const TRUNCATION_WARNING_THRESHOLD = 3;

export type ProgressCase = JobCase & { name: string; key: string };
export type ProgressRow = {
  suite: Suite; cases: ProgressCase[]; total: number; done: number;
  passed: number; failed: number; errors: number; truncated: number; notRun: number;
};
export type RunProgress = {
  rows: ProgressRow[]; total: number; done: number; passed: number; failed: number; notRun: number; calls: number;
  current?: { row: ProgressRow; entry: ProgressCase };
  warnings: string[];
};

export const STATE_LABELS: Record<CaseState, string> = {
  queued: 'Queued', running: 'Running', pass: 'Pass', fail: 'Fail',
  unscored: 'Unscored', error: 'Evaluator error', not_run: 'Not run'
};

export function isFailure(state: CaseState): boolean {
  return state === 'fail' || state === 'error';
}

/** Group a job's cases by category, in catalog order, with counts the UI reads directly. */
export function runProgress(job: Job, suites: Suite[]): RunProgress {
  const variants = new Set(job.cases.map((entry) => entry.variant));
  const rows: ProgressRow[] = [];
  for (const suite of suites) {
    const names = new Map(suite.cases.map((entry) => [entry.id, entry.name]));
    const cases = job.cases.filter((entry) => entry.suite === suite.id).map((entry) => ({
      ...entry,
      key: `${entry.variant}/${entry.id}`,
      name: `${names.get(entry.id) ?? entry.id}${variants.size > 1 ? ` (${entry.variant})` : ''}`
    }));
    if (!cases.length) continue;
    rows.push({
      suite, cases, total: cases.length,
      done: cases.filter((entry) => !UNFINISHED.includes(entry.state)).length,
      passed: cases.filter((entry) => entry.state === 'pass').length,
      failed: cases.filter((entry) => entry.state === 'fail').length,
      errors: cases.filter((entry) => entry.state === 'error').length,
      truncated: cases.filter((entry) => entry.truncated).length,
      notRun: cases.filter((entry) => entry.state === 'not_run').length
    });
  }
  const sum = (pick: (row: ProgressRow) => number) => rows.reduce((total, row) => total + pick(row), 0);
  const runningRow = rows.find((row) => row.cases.some((entry) => entry.state === 'running'));
  return {
    rows, total: sum((row) => row.total), done: sum((row) => row.done),
    passed: sum((row) => row.passed), failed: sum((row) => row.failed + row.errors), notRun: sum((row) => row.notRun),
    calls: job.cases.reduce((total, entry) => total + (entry.calls ?? 0), 0),
    current: runningRow && { row: runningRow, entry: runningRow.cases.find((entry) => entry.state === 'running')! },
    warnings: rows.filter((row) => row.truncated >= TRUNCATION_WARNING_THRESHOLD).map((row) =>
      `${row.truncated} ${row.suite.label} answers were cut off at the token limit; those scores may measure the limit, not the model.`)
  };
}
