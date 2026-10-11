import type { PageServerLoad } from './$types';
import { cases, currentJob, rows, runTimings, settings } from '../lib/server/bench';

export const load: PageServerLoad = () => {
  const config = settings();
  return {
    rows: rows(), job: currentJob(), cases: cases(), runTimings: runTimings(),
    sources: { freetoken: { configured: Boolean(config.localBase), defaultModel: config.localModel }, openrouter: { configured: config.openrouterReady }, compatible: { configured: true } }
  };
};
