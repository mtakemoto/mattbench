import { json } from '@sveltejs/kit';
import { models } from '../../../lib/server/bench';
import type { Source } from '../../../lib/contracts';

export async function GET({ url }: { url: URL }) {
  const source = url.searchParams.get('source');
  if (!['freetoken', 'openrouter', 'compatible'].includes(source || '')) return json({ error: 'Choose a model source.' }, { status: 400 });
  try {
    const options = await models(source as Source, url.searchParams.get('baseUrl') || '', (url.searchParams.get('q') || '').slice(0, 80));
    return json({ models: options });
  } catch (cause) {
    return json({ error: cause instanceof Error ? cause.message : 'Model catalog is unavailable.' }, { status: 502 });
  }
}
