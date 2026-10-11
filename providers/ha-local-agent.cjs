const path = require('node:path');
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
const { getLocalSettings } = require('../scripts/local-settings.cjs');

const MAX_REQUESTS = 4;
const MAX_TOOL_CALLS = 4;
const ALLOWED_TOOLS = new Set(['ha_search', 'ha_get_state']);

module.exports = class HaLocalAgent {
  id() {
    return `local-ha-agent:${getLocalSettings().model}`;
  }

  async callApi(prompt) {
    const { baseUrl, model } = getLocalSettings();
    const client = new Client({ name: 'mattbench-ha-agent', version: '0.1.0' });
    const transport = new StdioClientTransport({
      command: process.execPath,
      args: [path.join(__dirname, '..', 'scripts', 'ha-mock-mcp.cjs')],
      env: { MATTBENCH_HA_TRACE: process.env.MATTBENCH_HA_TRACE || '' },
      stderr: 'pipe',
    });
    const started = Date.now();
    const tokenUsage = { prompt: 0, completion: 0, total: 0, numRequests: 0 };
    const toolCalls = [];
    let concreteModel;
    try {
      await client.connect(transport);
      const { tools: listedTools } = await client.listTools();
      if (!listedTools.length || listedTools.some((tool) => !ALLOWED_TOOLS.has(tool.name))) {
        throw new Error('Synthetic MCP server exposed unexpected tools.');
      }
      const tools = listedTools.map((tool) => ({
        type: 'function',
        function: { name: tool.name, description: tool.description || '', parameters: tool.inputSchema },
      }));
      const messages = [{ role: 'user', content: prompt }];
      for (let step = 0; step < MAX_REQUESTS; step += 1) {
        const response = await fetch(`${baseUrl}/chat/completions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model, messages, tools, tool_choice: 'auto', temperature: 0, max_tokens: 512 }),
          signal: AbortSignal.timeout(120000),
        });
        if (!response.ok) throw new Error(`Local model returned HTTP ${response.status}.`);
        const data = await response.json();
        concreteModel = data.model || concreteModel;
        tokenUsage.numRequests += 1;
        for (const key of ['prompt', 'completion', 'total']) {
          const source = key === 'prompt' ? 'prompt_tokens' : key === 'completion' ? 'completion_tokens' : 'total_tokens';
          tokenUsage[key] += data.usage?.[source] || 0;
        }
        const message = data.choices?.[0]?.message;
        if (!message) throw new Error('Local model returned no message.');
        const calls = message.tool_calls || [];
        if (!calls.length) {
          if (typeof message.content !== 'string' || !message.content.trim()) {
            throw new Error('Local model returned no final answer.');
          }
          return {
            output: message.content,
            tokenUsage,
            latencyMs: Date.now() - started,
            cost: 0,
            metadata: { model, concreteModel, runtime: 'FreeToken', toolCalls, maxRequests: MAX_REQUESTS, maxToolCalls: MAX_TOOL_CALLS },
          };
        }
        if (toolCalls.length + calls.length > MAX_TOOL_CALLS) throw new Error('Tool-call limit reached.');
        messages.push({ role: 'assistant', content: message.content || null, tool_calls: calls });
        for (const call of calls) {
          const name = call.function?.name;
          if (!ALLOWED_TOOLS.has(name)) throw new Error('Model requested a tool outside the read-only allowlist.');
          let args;
          try { args = JSON.parse(call.function.arguments || '{}'); }
          catch { throw new Error('Model supplied invalid tool arguments.'); }
          const toolResult = await client.callTool({ name, arguments: args });
          toolCalls.push({ name, args, isError: Boolean(toolResult.isError) });
          messages.push({ role: 'tool', tool_call_id: call.id, content: JSON.stringify(toolResult.content) });
        }
      }
      throw new Error('Model request limit reached before a final answer.');
    } catch (error) {
      return { error: error.message, tokenUsage, latencyMs: Date.now() - started, metadata: { model, concreteModel, runtime: 'FreeToken', toolCalls } };
    } finally {
      await client.close();
    }
  }
};
