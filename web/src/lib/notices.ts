export type Notice = { id: string; tone: 'error' | 'warning'; title: string; body: string };

/** Everything that needs the owner's attention but must not interrupt the page. */
export function buildNotices(connectionError: string, historyError: string, warnings: string[], progressWarnings: string[]): Notice[] {
  const notices: Notice[] = [];
  if (connectionError) notices.push({ id: 'connection', tone: 'error', title: 'Console connection lost',
    body: `${connectionError} Retrying with backoff; a running benchmark continues independently.` });
  if (historyError) notices.push({ id: 'history', tone: 'error', title: 'Results unavailable',
    body: `${historyError} The last valid results stay on screen.` });
  for (const warning of progressWarnings) notices.push({ id: `progress:${warning}`, tone: 'warning', title: 'Answers cut off', body: warning });
  for (const warning of warnings) notices.push({ id: `report:${warning}`, tone: 'warning', title: 'Incomplete report', body: warning });
  return notices;
}
