const { getLocalSettings } = require('./local-settings.cjs');

async function main() {
  const { baseUrl, model } = getLocalSettings();
  const response = await fetch(`${baseUrl}/models`, {
    redirect: 'error',
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new Error(`Local model list returned HTTP ${response.status}.`);
  const body = await response.json();
  const ids = Array.isArray(body.data) ? body.data.map((entry) => entry.id) : [];
  if (!ids.includes(model)) {
    throw new Error('Configured local model ID does not match the server model list.');
  }
  console.log(`Local model preflight passed: ${model}`);
}

main().catch((error) => {
  console.error(`Local model preflight failed: ${error.message}`);
  process.exitCode = 2;
});
