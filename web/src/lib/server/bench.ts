import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { object, parseJob, type Job, type ModelOption, type RunInput, type Source } from '../contracts';
import { artifactDir, endpoint, launch, pythonJson } from './config';

export async function models(source: Source, customBase = '', query = ''): Promise<ModelOption[]> {
  const url = source === 'openrouter'
    ? 'https://openrouter.ai/api/v1/models'
    : `${endpoint(source, source === 'freetoken' ? '' : customBase)}/models`;
  const response = await fetch(url, {
    headers: source === 'openrouter' ? {} : { Authorization: 'Bearer local-no-secret' },
    signal: AbortSignal.timeout(8000), cache: 'no-store'
  });
  if (!response.ok) throw new Error(`Model catalog returned HTTP ${response.status}.`);
  const data = object(await response.json(), 'Model catalog');
  if (!Array.isArray(data.data)) throw new Error('Model catalog must contain a data array.');
  const needle = query.toLowerCase().trim();
  const options: ModelOption[] = [];
  for (const value of data.data) {
    const row = object(value, 'Model');
    if (typeof row.id !== 'string') throw new Error('Model catalog contains an invalid ID.');
    const name = typeof row.name === 'string' ? row.name : row.id;
    if (!`${row.id} ${name}`.toLowerCase().includes(needle)) continue;
    const pricing = row.pricing ? object(row.pricing, 'Model pricing') : {};
    options.push({ id: row.id, name, contextLength: typeof row.context_length === 'number' ? row.context_length : undefined,
      promptPrice: typeof pricing.prompt === 'string' ? pricing.prompt : undefined,
      completionPrice: typeof pricing.completion === 'string' ? pricing.completion : undefined });
    if (options.length === 80) break;
  }
  return options;
}

export function currentJob(): Job | null {
  const jobFile = join(artifactDir, 'job.json');
  if (!existsSync(jobFile)) return null;
  let job = parseJob(pythonJson('benchmark-worker.py', ['--status']));
  if (!job || job.status !== 'running') return job;
  // Progress may refine evaluation only; it can never overwrite billing/export or identity.
  if (['preparing', 'running'].includes(job.phase)) {
    const progressFile = join(artifactDir, `${job.id}.progress.json`);
    if (existsSync(progressFile)) {
      try {
        const progress = object(JSON.parse(readFileSync(progressFile, 'utf8')), 'Progress');
        const merged = { ...job };
        for (const field of ['currentCaseId', 'completedCases', 'completedCount', 'totalCases', 'message']) {
          if (field in progress) Object.assign(merged, { [field]: progress[field] });
        }
        job = parseJob(merged);
      } catch { /* Preserve durable state on a damaged progress artifact. */ }
    }
  }
  return job;
}

export function startJob(input: RunInput): Job {
  // Python owns validation, frozen plan, atomic job writes and the single-run OS lock.
  return launch(input);
}
