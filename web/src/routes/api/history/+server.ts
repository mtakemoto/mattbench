import { json } from '@sveltejs/kit';
import { history, historyRevision } from '../../../lib/server/results';

export function GET({ url }: { url: URL }) {
  if (url.searchParams.get('revision') === historyRevision()) return new Response(null, { status: 304 });
  return json(history());
}
