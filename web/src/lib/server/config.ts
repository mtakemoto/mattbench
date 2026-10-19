import { execFileSync } from 'node:child_process';
import { resolve, join } from 'node:path';
import { object, parseJob, parseSuite, type Job, type RunInput, type Source, type Suite } from '../contracts';

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

export type Configuration = { settings: { localBase: string; localModel: string; openrouterReady: boolean }; suites: Suite[] };

/** Non-secret settings and the registered suites, read from scripts/console_bridge.py. */
export function configuration(): Configuration {
  const description = object(pythonJson('console_bridge.py', ['--describe']), 'Configuration');
  const settings = object(description.settings, 'Settings');
  if (typeof settings.localBase !== 'string' || typeof settings.localModel !== 'string' || typeof settings.openrouterReady !== 'boolean' || !Array.isArray(description.suites)) {
    throw new Error('Invalid shared settings contract.');
  }
  return { settings: settings as Configuration['settings'], suites: description.suites.map(parseSuite) };
}

/** Validated endpoint for a source; Python owns the loopback/private-network rules. */
export function endpoint(source: Source, baseUrl: string): string {
  const validated = object(pythonJson('console_bridge.py', ['--endpoint'], { source, baseUrl }), 'Endpoint');
  if (typeof validated.baseUrl !== 'string') throw new Error('Shared endpoint validation failed.');
  return validated.baseUrl;
}

export function launch(input: RunInput): Job {
  const job = parseJob(pythonJson('benchmark-worker.py', ['--start'], input));
  if (!job) throw new Error('Benchmark worker did not publish a job.');
  return job;
}
