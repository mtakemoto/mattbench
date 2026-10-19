import { existsSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { object, parseRow, type History } from '../contracts';
import { root } from './config';

/** Written by scripts/inspect-report.py after every run. */
const summaryPath = join(root, 'artifacts', 'inspect', 'summary.json');
let cached: History | null = null;

export function historyRevision(): string {
  if (!existsSync(summaryPath)) return 'missing';
  const stat = statSync(summaryPath);
  return `${stat.mtimeMs}:${stat.ctimeMs}:${stat.size}`;
}

export function history(): History {
  const revision = historyRevision();
  if (cached?.revision === revision) return cached;
  const warnings: string[] = [];
  let rows: History['rows'] = [];
  if (existsSync(summaryPath)) {
    try {
      const summary = object(JSON.parse(readFileSync(summaryPath, 'utf8')), 'Summary');
      if (summary.schema_version !== 1 || !Array.isArray(summary.rows)) throw new Error('Invalid summary schema.');
      for (const entry of summary.rows) {
        try { rows.push(parseRow(entry)); }
        catch { warnings.push('A damaged summary row was skipped; report is incomplete.'); }
      }
      if (summary.warnings !== undefined) {
        if (!Array.isArray(summary.warnings) || summary.warnings.some((entry) => typeof entry !== 'string')) throw new Error('Invalid summary warnings.');
        warnings.push(...summary.warnings);
      }
    } catch {
      rows = cached?.rows || [];
      warnings.push('Summary is unreadable; showing the last valid results when available.');
    }
  }
  cached = { revision, rows, warnings: [...new Set(warnings)] };
  return cached;
}
