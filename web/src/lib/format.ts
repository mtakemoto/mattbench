import { SOURCES, type Source, type Suite } from './contracts';

export const SOURCE_LABELS: Record<Source, string> = { freetoken: 'FreeToken', openrouter: 'OpenRouter', compatible: 'Other endpoint' };

/** Inspect names models `openai-api/<source>/<model id>`. */
export function sourceOf(model: string): Source {
  return SOURCES.find((source) => model.startsWith(`openai-api/${source}/`)) ?? 'freetoken';
}
export function modelName(model: string): string {
  return model.replace(/^openai-api\/[^/]+\//, '');
}
export function shortModelName(model: string, limit = 31): string {
  const text = modelName(model);
  return text.length > limit ? `${text.slice(0, limit - 2)}…` : text;
}
export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value);
}
export function formatSeconds(value?: number | null): string {
  return value == null ? '—' : `${value.toFixed(value < 10 ? 1 : 0)}s`;
}
export function formatRunTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Time not reported' : new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short'
  }).format(date);
}
export function outcomeLabel(passed: boolean | null | undefined): 'PASS' | 'FAIL' | 'UNSCORED' {
  return passed === true ? 'PASS' : passed === false ? 'FAIL' : 'UNSCORED';
}
/** `plural(3, 'category', 'categories')`; the plural form defaults to singular + 's'. */
export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

/** "17 cases · Smoke questions, Smart home" — what a recorded run covered, from its sample IDs. */
export function coverageNamer(suites: Suite[]): (sampleIds: string[]) => string {
  const suiteOf = new Map(suites.flatMap((suite) => suite.cases.map((entry) => [entry.id, suite] as const)));
  return (sampleIds) => {
    const covered = suites.filter((suite) => sampleIds.some((id) => suiteOf.get(id) === suite));
    const names = covered.length === suites.length ? 'all categories' : covered.map((suite) => suite.label).join(', ');
    return `${plural(sampleIds.length, 'case')} · ${names || 'pilot tasks'}`;
  };
}

/** Display names for suite IDs and case IDs, which share one progress namespace. */
export function taskNamer(suites: Suite[]): (id: string) => string {
  const names = new Map<string, string>();
  for (const suite of suites) {
    names.set(suite.id, suite.label);
    for (const entry of suite.cases) names.set(entry.id, entry.name);
  }
  return (id) => names.get(id) ?? id.replaceAll('_', ' ');
}
