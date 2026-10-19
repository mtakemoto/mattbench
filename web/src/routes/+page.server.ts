import type { PageServerLoad } from './$types';
import { currentJob } from '../lib/server/bench';
import { configuration } from '../lib/server/config';
import { historyRevision } from '../lib/server/results';

export const load: PageServerLoad = () => {
  const config = configuration();
  return {
    job: currentJob(), suites: config.suites, revision: historyRevision(),
    sources: { freetoken: { configured: Boolean(config.settings.localBase), defaultModel: config.settings.localModel }, openrouter: { configured: config.settings.openrouterReady }, compatible: { configured: true } }
  };
};
