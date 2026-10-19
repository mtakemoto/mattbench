import { json } from '@sveltejs/kit';
import { models, startJob } from '../../../lib/server/bench';
import { isSource } from '../../../lib/contracts';

export async function POST({ request, url }: { request: Request; url: URL }) {
  if (request.headers.get('origin') !== url.origin || !request.headers.get('content-type')?.startsWith('application/json')) {
    return json({ error: 'Use the local app to start a run.' }, { status: 403 });
  }
  try {
    const input = await request.json();
    if (!isSource(input.source)) throw new Error('Choose a model source.');
    if (typeof input.model !== 'string') throw new Error('Choose a model.');
    const available = await models(input.source, input.baseUrl || '', input.model);
    if (!available.some((option) => option.id === input.model)) throw new Error('The selected model is no longer in this source catalog. Refresh the list.');
    const job = startJob({
      source: input.source, model: input.model, variants: input.variants, selection: input.selection,
      baseUrl: input.baseUrl, maxCalls: input.maxCalls, capUsd: input.capUsd, capConfirmed: input.capConfirmed
    });
    return json({ job }, { status: 202 });
  } catch (cause) {
    return json({ error: cause instanceof Error ? cause.message : 'Could not start the run.' }, { status: 400 });
  }
}
