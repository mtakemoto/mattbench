import { json } from '@sveltejs/kit';
import { currentJob } from '../../../lib/server/bench';
import { historyRevision } from '../../../lib/server/results';

export function GET() {
  return json({ job: currentJob(), revision: historyRevision() });
}
