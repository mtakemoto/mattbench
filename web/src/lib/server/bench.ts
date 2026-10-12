import { existsSync, readFileSync, readdirSync, mkdirSync, writeFileSync, renameSync, openSync, closeSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { spawn } from 'node:child_process';

export const root = resolve(process.cwd(), '..');
const artifactDir = join(root, 'artifacts', 'web');
const jobFile = join(artifactDir, 'job.json');

export type Source = 'freetoken' | 'openrouter' | 'compatible';
export type ModelOption = { id: string; name: string; contextLength?: number; promptPrice?: string; completionPrice?: string };
export type Case = { id: string; name: string; category: string; suite: 'smoke' | 'ha'; fixture: string; maxModelCalls?: number };
export type Job = { id: string; status: 'running' | 'complete' | 'failed' | 'interrupted'; source: Source; model: string; variant: string; caseId: string; startedAt: string; finishedAt?: string; error?: string; pid?: number; phase: 'validating' | 'preparing' | 'running' | 'billing' | 'exporting' | 'complete' | 'failed' | 'interrupted'; currentCaseId?: string; completedCases: { caseId: string; status: 'complete' | 'failed'; passed?: boolean; modelCalls?: number; message?: string }[]; completedCount: number; totalCases: number; message: string; updatedAt: string };

export function cases(): Case[] {
  const smoke = JSON.parse(readFileSync(join(root, 'tasks', 'smoke.json'), 'utf8')) as { id: string; name?: string; category: string }[];
  const ha = JSON.parse(readFileSync(join(root, 'tasks', 'inspect-ha-cases.json'), 'utf8')) as { id: string; name: string; category: string; fixture: string; max_model_calls: number }[];
  return [
    ...smoke.map((entry) => ({ id: entry.id, name: entry.name || entry.id.replaceAll('_', ' '), category: entry.category, suite: 'smoke' as const, fixture: 'tasks/smoke.json' })),
    ...ha.map((entry) => ({ id: entry.id, name: entry.name, category: entry.category, suite: 'ha' as const, fixture: entry.fixture, maxModelCalls: entry.max_model_calls }))
  ];
}

export function runTimings() {
  const directory = join(root, 'artifacts', 'inspect', 'ha-timing');
  if (!existsSync(directory)) return [];
  const latest = new Map<string, { case_id: string; status: string; setup_seconds: number; evaluation_seconds: number; teardown_seconds: number; total_wall_seconds: number }>();
  for (const file of readdirSync(directory).filter((file) => file.endsWith('.json')).sort().reverse()) {
    const item = JSON.parse(readFileSync(join(directory, file), 'utf8'));
    if (latest.has(item.case_id)) continue;
    latest.set(item.case_id, { case_id: item.case_id, status: item.status, setup_seconds: item.setup_seconds,
      evaluation_seconds: item.evaluation_seconds, teardown_seconds: item.teardown_seconds,
      total_wall_seconds: item.total_wall_seconds });
  }
  return [...latest.values()];
}

function envFile(): Record<string, string> {
  const path = join(root, '.env');
  if (!existsSync(path)) return {};
  return Object.fromEntries(readFileSync(path, 'utf8').split(/\r?\n/).map((line) => {
    const match = line.match(/^([A-Z][A-Z0-9_]*)=(.*)$/);
    if (!match) return ['', ''];
    let value = match[2].trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    return [match[1], value];
  }).filter(([key]) => key));
}

export function settings() {
  const values = envFile();
  return {
    localBase: process.env.MATTBENCH_LOCAL_BASE_URL || values.MATTBENCH_LOCAL_BASE_URL || 'http://127.0.0.1:1919/v1',
    localModel: process.env.MATTBENCH_LOCAL_MODEL || values.MATTBENCH_LOCAL_MODEL || '',
    openrouterReady: Boolean(process.env.OPENROUTER_API_KEY || values.OPENROUTER_API_KEY),
    openrouterKey: process.env.OPENROUTER_API_KEY || values.OPENROUTER_API_KEY || ''
  };
}

export function compatibleBase(raw: string): string {
  const url = new URL(raw);
  const host = url.hostname.replace(/^\[|\]$/g, '');
  const ipv4 = host.split('.').map(Number);
  const privateV4 = ipv4.length === 4 && ipv4.every((part) => Number.isInteger(part) && part >= 0 && part <= 255)
    && (ipv4[0] === 10 || ipv4[0] === 127 || (ipv4[0] === 172 && ipv4[1] >= 16 && ipv4[1] <= 31) || (ipv4[0] === 192 && ipv4[1] === 168));
  const localV6 = host === '::1' || /^f[cd][0-9a-f:]+$/i.test(host);
  if (url.protocol !== 'http:' || !['/v1', '/v1/'].includes(url.pathname) || url.username || url.password || url.search || url.hash || !(host === 'localhost' || privateV4 || localV6)) {
    throw new Error('Use an HTTP /v1 endpoint on localhost or a literal private network address.');
  }
  return url.toString().replace(/\/$/, '');
}

async function readJson(url: string, headers: Record<string, string> = {}) {
  const response = await fetch(url, { headers, signal: AbortSignal.timeout(8000), cache: 'no-store' });
  if (!response.ok) throw new Error(`Model catalog returned HTTP ${response.status}.`);
  return response.json();
}

export async function models(source: Source, customBase = '', query = ''): Promise<ModelOption[]> {
  const config = settings();
  const data = source === 'openrouter'
    ? await readJson('https://openrouter.ai/api/v1/models')
    : await readJson(`${compatibleBase(source === 'freetoken' ? config.localBase : customBase)}/models`, { Authorization: 'Bearer local-no-secret' });
  const options: ModelOption[] = (Array.isArray(data.data) ? data.data : [])
    .filter((row: Record<string, unknown>) => typeof row.id === 'string')
    .map((row: Record<string, unknown>) => ({
      id: String(row.id), name: typeof row.name === 'string' ? row.name : String(row.id),
      contextLength: typeof row.context_length === 'number' ? row.context_length : undefined,
      promptPrice: typeof (row.pricing as Record<string, unknown> | undefined)?.prompt === 'string' ? String((row.pricing as Record<string, unknown>).prompt) : undefined,
      completionPrice: typeof (row.pricing as Record<string, unknown> | undefined)?.completion === 'string' ? String((row.pricing as Record<string, unknown>).completion) : undefined
    }));
  const needle = query.toLowerCase().trim();
  return options.filter((option) => `${option.id} ${option.name}`.toLowerCase().includes(needle)).slice(0, 80);
}

export function rows() {
  const path = join(root, 'artifacts', 'inspect', 'summary.json');
  if (!existsSync(path)) return [];
  const data = JSON.parse(readFileSync(path, 'utf8'));
  if (!Array.isArray(data.rows)) return [];
  return data.rows.map((row: Record<string, unknown>) => ({
    task: row.task, run_id: row.run_id, launcher_run_id: row.launcher_run_id, sample_id: row.sample_id, category: row.category,
    prompt_variant: row.prompt_variant, status: row.status, model: row.model,
    concrete_response_model: row.concrete_response_model, routed_models: row.routed_models, providers: row.providers, passed: row.passed,
    latency_seconds: row.latency_seconds, usage: row.usage, tool_calls: row.tool_calls, model_calls: row.model_calls,
    score_metadata: row.score_metadata, score_explanation: row.score_explanation, started_at: row.started_at, fixture: row.fixture,
    inference: row.inference, inspect_version: row.inspect_version, task_version: row.task_version,
    log_file: row.log_file, run_timing: row.run_timing
  }));
}

function writeJob(job: Job) {
  mkdirSync(artifactDir, { recursive: true });
  const temporary = `${jobFile}.tmp`;
  writeFileSync(temporary, JSON.stringify(job, null, 2) + '\n');
  renameSync(temporary, jobFile);
}

export function currentJob(): Job | null {
  if (!existsSync(jobFile)) return null;
  const job: Job = JSON.parse(readFileSync(jobFile, 'utf8'));
  const progressPath = join(artifactDir, `${job.id}.progress.json`);
  if (job.status === 'running' && existsSync(progressPath)) {
    try {
      const progress = JSON.parse(readFileSync(progressPath, 'utf8'));
      Object.assign(job, progress);
    } catch { /* Keep the last durable job snapshot while a progress write is in flight. */ }
  }
  if (job.status === 'running' && Date.now() - Date.parse(job.startedAt) > 10 * 60_000) {
    try { if (job.pid) process.kill(job.pid, 0); else throw new Error('worker ended'); }
    catch {
      job.status = 'interrupted'; job.phase = 'interrupted'; job.message = 'Worker stopped before the run completed.';
      job.updatedAt = job.finishedAt = new Date().toISOString(); writeJob(job);
    }
  }
  return job;
}

export function startJob(input: { source: Source; model: string; variant: 'base' | 'careful' | 'both'; caseId: string; baseUrl?: string; maxCalls: number; capUsd?: number; capConfirmed?: boolean }): Job {
  if (currentJob()?.status === 'running') throw new Error('A benchmark is already running.');
  if (!/^[\w./:-]{1,160}$/.test(input.model)) throw new Error('Choose a valid model ID from the catalog.');
  if (!['base', 'careful', 'both'].includes(input.variant)) throw new Error('Choose a prompt variant.');
  const haCase = cases().find((entry) => entry.id === input.caseId && entry.suite === 'ha');
  if (input.caseId !== 'all' && input.caseId !== 'smoke' && !haCase) throw new Error('Choose a pinned benchmark case.');
  const allCases = input.caseId === 'all';
  if (allCases && input.variant !== 'base') throw new Error('The all-suite run uses the base prompt variant.');
  if (haCase && input.variant !== 'base') throw new Error('Home Assistant cases currently use the base prompt.');
  const haCases = cases().filter((entry) => entry.suite === 'ha');
  if (haCases.some((entry) => !Number.isInteger(entry.maxModelCalls) || entry.maxModelCalls! < 1)) throw new Error('Every HA case needs a positive model call limit.');
  const expectedCalls = allCases ? 2 + haCases.reduce((sum, entry) => sum + entry.maxModelCalls!, 0) : haCase ? haCase.maxModelCalls! : input.variant === 'both' ? 4 : 2;
  if (input.maxCalls !== expectedCalls) throw new Error(allCases
    ? `Run-all is capped at ${expectedCalls} model calls: 2 smoke calls plus each HA case's pinned limit.`
    : `This selection allows at most ${expectedCalls} model calls.`);
  const config = settings();
  const base = input.source === 'openrouter' ? '' : compatibleBase(input.source === 'freetoken' ? config.localBase : input.baseUrl || '');
  if (input.source === 'openrouter' && (!config.openrouterReady || !input.capConfirmed || typeof input.capUsd !== 'number' || !(input.capUsd > 0 && input.capUsd <= 20))) {
    throw new Error('OpenRouter needs an API key, an active workspace cap up to $20, and explicit cap confirmation.');
  }
  const id = new Date().toISOString().replace(/[^0-9]/g, '').slice(0, 17);
  const count = allCases ? haCases.length + 1 : 1;
  const now = new Date().toISOString();
  const job: Job = { id, status: 'running', phase: allCases ? 'validating' : 'preparing', currentCaseId: allCases ? undefined : input.caseId, source: input.source, model: input.model, variant: input.variant, caseId: input.caseId, startedAt: now, updatedAt: now, completedCases: [], completedCount: 0, totalCases: count, message: allCases ? 'Validating pinned suite' : `Preparing ${haCase?.name || 'smoke set'}` };
  mkdirSync(artifactDir, { recursive: true });
  const logFd = openSync(join(artifactDir, `${id}.log`), 'w');
  const args = allCases
    ? [join(root, 'scripts', 'run-inspect-suite.py'), '--source', input.source, '--model', input.model, '--run-id', id, '--progress-file', join(artifactDir, `${id}.progress.json`)]
    : haCase
    ? [join(root, 'scripts', 'run-inspect-ha-pilot.py'), '--case', input.caseId, '--source', input.source, '--model', input.model, '--run-id', id, '--progress-file', join(artifactDir, `${id}.progress.json`)]
    : [join(root, 'scripts', 'run-inspect-selected.py'), '--source', input.source, '--model', input.model, '--variant', input.variant, '--max-calls', String(expectedCalls), '--run-id', id];
  if (base) args.push('--base-url', base);
  if (input.source === 'openrouter') args.push('--cap-usd', String(input.capUsd));
  const child = spawn(join(root, '.venv', 'bin', 'python'), args, {
    cwd: root, stdio: ['ignore', logFd, logFd], env: {
      PATH: process.env.PATH || '', HOME: process.env.HOME || '',
      ...(input.source === 'openrouter' ? { OPENROUTER_API_KEY: config.openrouterKey } : {})
    }
  });
  closeSync(logFd);
  job.pid = child.pid;
  writeJob(job);
  child.on('error', () => {
    writeJob({ ...job, status: 'failed', phase: 'failed', updatedAt: new Date().toISOString(), finishedAt: new Date().toISOString(), error: 'Could not start Inspect. Install the Python dependencies in .venv.', message: 'Could not start benchmark.' });
  });
  child.on('exit', (code) => {
    const progressPath = join(artifactDir, `${id}.progress.json`);
    let progress = {};
    try { progress = JSON.parse(readFileSync(progressPath, 'utf8')); } catch { /* no suite progress file for single-case runs */ }
    const caseResults = allCases ? {} : { completedCases: [{ caseId: input.caseId, status: code === 0 ? 'complete' as const : 'failed' as const }], completedCount: 1, totalCases: 1 };
    const exporting: Job = { ...job, ...progress, ...caseResults, pid: undefined, phase: 'exporting', message: 'Exporting Inspect results', updatedAt: new Date().toISOString() };
    const exportResults = (billingOk: boolean) => {
      writeJob(exporting);
      const exporter = spawn(join(root, '.venv', 'bin', 'python'), [join(root, 'scripts', 'inspect-report.py')], { cwd: root, stdio: 'ignore', env: { PATH: process.env.PATH || '', HOME: process.env.HOME || '' } });
      exporter.on('exit', (exportCode) => {
        const ok = code === 0 && exportCode === 0;
        const finishedAt = new Date().toISOString();
        const resultRows = rows().filter((row: Record<string, unknown>) => row.launcher_run_id === id);
        const completedCases = exporting.completedCases.map((entry) => {
          const selected = resultRows.filter((row: Record<string, unknown>) => entry.caseId === 'smoke' ? ['strawberry_r_count', 'car_wash_transport'].includes(String(row.sample_id)) : row.sample_id === entry.caseId);
          return selected.length ? { ...entry, passed: selected.every((row: Record<string, unknown>) => row.passed === true), modelCalls: selected.reduce((sum: number, row: Record<string, unknown>) => sum + Number(row.model_calls || 0), 0) } : entry;
        });
        writeJob({ ...exporting, completedCases, status: ok ? 'complete' : 'failed', phase: ok ? 'complete' : 'failed', finishedAt, updatedAt: finishedAt, message: ok ? billingOk ? 'Run and export complete.' : 'Run finished; billed cost unavailable.' : 'Run or export failed; see the ignored local run log.', error: ok ? undefined : code !== 0 ? 'Inspect stopped. See the ignored local run log for details.' : 'Could not export Inspect results.' });
      });
      exporter.on('error', () => writeJob({ ...exporting, status: 'failed', phase: 'failed', finishedAt: new Date().toISOString(), updatedAt: new Date().toISOString(), message: 'Could not export Inspect results.', error: 'Could not export Inspect results.' }));
    };
    if (input.source === 'openrouter') {
      writeJob({ ...exporting, phase: 'billing', message: 'Reading billed OpenRouter cost' });
      const billing = spawn(join(root, '.venv', 'bin', 'python'), [join(root, 'scripts', 'openrouter-billing.py'), '--run-id', id], { cwd: root, stdio: 'ignore', env: { PATH: process.env.PATH || '', HOME: process.env.HOME || '', OPENROUTER_API_KEY: config.openrouterKey } });
      let billingFinished = false;
      const finishBilling = (ok: boolean) => { if (!billingFinished) { billingFinished = true; exportResults(ok); } };
      billing.on('exit', (billingCode) => finishBilling(billingCode === 0));
      billing.on('error', () => finishBilling(false));
    } else exportResults(true);
  });
  return job;
}
