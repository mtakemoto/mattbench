const fs = require('node:fs');
const path = require('node:path');

// Read only the two local settings. Do not load unrelated credentials from .env.
function readLocalEnv() {
  const filename = path.join(__dirname, '..', '.env');
  if (!fs.existsSync(filename)) return {};
  const values = {};
  for (const line of fs.readFileSync(filename, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^(MATTBENCH_LOCAL_BASE_URL|MATTBENCH_LOCAL_MODEL)=(.*)$/);
    if (match) values[match[1]] = match[2].trim();
  }
  return values;
}

function getLocalSettings() {
  const envFile = readLocalEnv();
  const baseUrlText = process.env.MATTBENCH_LOCAL_BASE_URL || envFile.MATTBENCH_LOCAL_BASE_URL;
  const model = process.env.MATTBENCH_LOCAL_MODEL || envFile.MATTBENCH_LOCAL_MODEL;
  if (!baseUrlText || !model) {
    throw new Error('Set MATTBENCH_LOCAL_BASE_URL and MATTBENCH_LOCAL_MODEL in .env or the environment.');
  }
  let url;
  try {
    url = new URL(baseUrlText);
  } catch {
    throw new Error('MATTBENCH_LOCAL_BASE_URL must be a valid loopback URL ending in /v1.');
  }
  if (
    url.protocol !== 'http:' ||
    !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) ||
    url.username || url.password || url.search || url.hash ||
    !/^\/v1\/?$/.test(url.pathname)
  ) {
    throw new Error('MATTBENCH_LOCAL_BASE_URL must use plain HTTP on loopback and end in /v1.');
  }
  if (!/^[A-Za-z0-9._/-]+$/.test(model)) {
    throw new Error('MATTBENCH_LOCAL_MODEL has unsupported characters.');
  }
  return { baseUrl: url.href.replace(/\/$/, ''), model };
}

module.exports = { getLocalSettings };
