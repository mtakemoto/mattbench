import { json } from '@sveltejs/kit';
import { cases, currentJob, rows, runTimings, settings } from '../../../lib/server/bench';

export function GET() {
  const config = settings();
  return json({
    rows: rows(), job: currentJob(), cases: cases(), runTimings: runTimings(),
    sources: {
      freetoken: { configured: Boolean(config.localBase), defaultModel: config.localModel },
      openrouter: { configured: config.openrouterReady },
      compatible: { configured: true }
    }
  });
}
