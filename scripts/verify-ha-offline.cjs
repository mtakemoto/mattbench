// End-to-end harness check with a deterministic fake chat API on loopback.
// This verifies Promptfoo's MCP round trip; it says nothing about model quality.
const http = require('node:http');
const { spawn } = require('node:child_process');
const path = require('node:path');

const model = 'mattbench-offline-tool-stub';
let requestCount = 0;
const server = http.createServer(async (request, response) => {
  const send = (status, value) => {
    response.writeHead(status, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify(value));
  };
  if (request.method === 'GET' && request.url === '/v1/models') {
    send(200, { object: 'list', data: [{ id: model }] });
    return;
  }
  if (request.method !== 'POST' || request.url !== '/v1/chat/completions') {
    send(404, { error: 'Not found' });
    return;
  }
  let body = '';
  for await (const chunk of request) body += chunk;
  const input = JSON.parse(body);
  const tools = new Set((input.tools || []).map((tool) => tool.function?.name));
  const toolReplies = (input.messages || []).filter((message) => message.role === 'tool');
  let message;
  if (!toolReplies.length) {
    const name = [...tools].find((tool) => tool.endsWith('ha_search'));
    if (!name) return send(400, { error: 'Missing ha_search tool' });
    message = { role: 'assistant', content: null, tool_calls: [{ id: 'search_1', type: 'function', function: { name, arguments: JSON.stringify({ query: 'North Room', domain_filter: 'climate' }) } }] };
  } else if (toolReplies.length === 1) {
    const name = [...tools].find((tool) => tool.endsWith('ha_get_state'));
    if (!name) return send(400, { error: 'Missing ha_get_state tool' });
    message = { role: 'assistant', content: null, tool_calls: [{ id: 'state_1', type: 'function', function: { name, arguments: JSON.stringify({ entity_id: 'climate.north_room_coordinator' }) } }] };
  } else {
    const stateReply = toolReplies.at(-1).content || '';
    const blocks = JSON.parse(stateReply);
    const state = JSON.parse(blocks.find((block) => block.type === 'text')?.text || '{}');
    if (state.data?.attributes?.temperature !== 70) return send(400, { error: 'Missing expected tool result' });
    message = { role: 'assistant', content: '70' };
  }
  requestCount += 1;
  send(200, {
    id: `chatcmpl-offline-${requestCount}`,
    object: 'chat.completion',
    created: 0,
    model,
    choices: [{ index: 0, message, finish_reason: message.tool_calls ? 'tool_calls' : 'stop' }],
    usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
  });
});

server.listen(0, '127.0.0.1', () => {
  const address = server.address();
  const child = spawn('bash', [path.join(__dirname, 'run-ha-local.sh')], {
    cwd: path.join(__dirname, '..'),
    env: {
      ...process.env,
      MATTBENCH_LOCAL_BASE_URL: `http://127.0.0.1:${address.port}/v1`,
      MATTBENCH_LOCAL_MODEL: model,
      MATTBENCH_HA_OUTPUT_BASENAME: 'promptfoo-ha-offline',
    },
    stdio: 'inherit',
  });
  child.on('exit', (code) => {
    server.close();
    if (code || requestCount !== 3) {
      console.error(`Offline HA harness failed: exit=${code}, model_requests=${requestCount}`);
      process.exitCode = 1;
    } else {
      console.log('Offline HA harness passed: 3 fake model requests, search + state + answer.');
    }
  });
});
