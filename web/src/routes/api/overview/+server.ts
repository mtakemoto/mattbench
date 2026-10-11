import { json } from '@sveltejs/kit';
import { currentJob, rows, settings } from '../../../lib/server/bench';

export function GET() {
  const config = settings();
  return json({
    rows: rows(), job: currentJob(),
    sources: {
      freetoken: { configured: Boolean(config.localBase), defaultModel: config.localModel },
      openrouter: { configured: config.openrouterReady },
      compatible: { configured: true }
    }
  });
}
