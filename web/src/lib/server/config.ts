import { execFileSync } from 'node:child_process';
import { resolve, join } from 'node:path';
import { object, parseCase, parseJob, type BenchmarkCase, type Job, type RunInput, type Source } from '../contracts';

export const root = resolve(process.cwd(), '..');
export const artifactDir = join(root, 'artifacts', 'web');

export function pythonJson(script: string, args: string[], input?: unknown): unknown {
  let output: string;
  try {
    output = execFileSync(join(root, '.venv', 'bin', 'python'), [join(root, 'scripts', script), ...args], {
      cwd: root, encoding: 'utf8', timeout: 15000, maxBuffer: 2 * 1024 * 1024,
      input: input === undefined ? undefined : JSON.stringify(input), stdio: ['pipe', 'pipe', 'pipe']
    });
  } catch (cause) {
    const failure = cause as { stdout?: string | Buffer };
    if (failure.stdout) {
      try {
        const diagnostic = object(JSON.parse(String(failure.stdout)), 'Worker diagnostic');
        if (typeof diagnostic.error === 'string') throw new Error(diagnostic.error);
      } catch (diagnostic) {
        if (diagnostic instanceof Error && !(diagnostic instanceof SyntaxError)) throw diagnostic;
      }
    }
    throw new Error('Benchmark configuration worker failed. Check the local Python installation.');
  }
  try { return JSON.parse(output); }
  catch { throw new Error('Benchmark configuration worker returned invalid JSON.'); }
}

export function configuration(): { settings: { localBase: string; localModel: string; openrouterReady: boolean }; cases: BenchmarkCase[] } {
  const description = object(pythonJson('execution_plan.py', ['--describe']), 'Configuration');
  const settings = object(description.settings, 'Settings');
  if (typeof settings.localBase !== 'string' || typeof settings.localModel !== 'string' || typeof settings.openrouterReady !== 'boolean' || !Array.isArray(description.cases)) {
    throw new Error('Invalid shared settings contract.');
  }
  return { settings: settings as { localBase: string; localModel: string; openrouterReady: boolean }, cases: description.cases.map(parseCase) };
}

export function endpoint(source: Source, baseUrl: string): string {
  const validated = object(pythonJson('execution_plan.py', ['--request-json'], {
    source, model: 'catalog-probe', variant: 'base', caseId: 'smoke', baseUrl
  }), 'Execution request');
  const settings = object(validated.settings, 'Execution settings');
  if (typeof settings.baseUrl !== 'string') throw new Error('Shared endpoint validation failed.');
  return settings.baseUrl;
}

export function launch(input: RunInput): Job {
  const job = parseJob(pythonJson('benchmark-worker.py', ['--start'], input));
  if (!job) throw new Error('Benchmark worker did not publish a job.');
  return job;
}
