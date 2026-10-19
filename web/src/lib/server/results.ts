import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { object, parseRow, parseTiming, type CaseTiming, type History } from '../contracts';
import { root } from './config';

const directory = join(root, 'artifacts', 'inspect');
const summaryPath = join(directory, 'summary.json');
const timingDirectory = join(directory, 'ha-timing');
let cached: History | null = null;
const timingCache = new Map<string, { fingerprint: string; timing?: CaseTiming; warning?: string }>();

export function historyRevision(): string {
  const revision = [summaryPath, timingDirectory].map((path) => {
    if (!existsSync(path)) return 'missing';
    const stat = statSync(path);
    return `${stat.mtimeMs}:${stat.ctimeMs}:${stat.size}`;
  });
  return revision.join('|');
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
  const latest = new Map<string, CaseTiming>();
  const files = existsSync(timingDirectory) ? readdirSync(timingDirectory).filter((file) => file.endsWith('.json')).sort().reverse() : [];
  for (const file of files) {
    const path = join(timingDirectory, file);
    try {
      const stat = statSync(path);
      const fingerprint = `${stat.mtimeMs}:${stat.ctimeMs}:${stat.size}`;
      let item = timingCache.get(file);
      if (!item || item.fingerprint !== fingerprint) {
        try { item = { fingerprint, timing: parseTiming(JSON.parse(readFileSync(path, 'utf8'))) }; }
        catch { item = { fingerprint, warning: 'A damaged timing artifact was skipped; report is incomplete.' }; }
        timingCache.set(file, item);
      }
      if (item.warning) warnings.push(item.warning);
      if (item.timing && !latest.has(item.timing.case_id)) latest.set(item.timing.case_id, item.timing);
    } catch {
      warnings.push('A timing artifact became unavailable; report is incomplete.');
    }
  }
  for (const file of timingCache.keys()) if (!files.includes(file)) timingCache.delete(file);
  cached = { revision, rows, runTimings: [...latest.values()], warnings: [...new Set(warnings)] };
  return cached;
}
