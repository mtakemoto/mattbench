import type { PageServerLoad } from './$types';
import { currentJob, rows, settings } from '../lib/server/bench';

export const load: PageServerLoad = () => {
  const config = settings();
  return {
    rows: rows(), job: currentJob(),
    sources: { freetoken: { configured: Boolean(config.localBase), defaultModel: config.localModel }, openrouter: { configured: config.openrouterReady }, compatible: { configured: true } }
  };
};
