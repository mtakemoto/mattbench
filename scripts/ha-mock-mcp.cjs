// A deliberately small read-only ha-mcp approximation over Synthetic Home YAML.
// It has no HTTP client and accepts no server address or token.
const fs = require('node:fs');
const { McpServer } = require('@modelcontextprotocol/sdk/server/mcp.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const z = require('zod/v4');
const { inventory, byId, areaNames, stateRecord } = require('./ha-fixture.cjs');

const server = new McpServer({ name: 'mattbench-synthetic-ha', version: '0.1.0' });
const annotation = { readOnlyHint: true, destructiveHint: false, openWorldHint: false };
function record(name, args) {
  if (process.env.MATTBENCH_HA_TRACE) {
    fs.appendFileSync(process.env.MATTBENCH_HA_TRACE, `${JSON.stringify({ name, args })}\n`);
  }
}
function result(data) {
  return { content: [{ type: 'text', text: JSON.stringify(data) }] };
}

server.registerTool('ha_search', {
  description: 'Search Home Assistant entities by name or ID. Filter by domain or area. Read only.',
  annotations: annotation,
  inputSchema: {
    query: z.string().optional().describe('Name fragment or entity ID'),
    domain_filter: z.string().optional().describe('Entity domain, such as climate or sensor'),
    area_filter: z.string().optional().describe('Area name'),
  },
}, async (args) => {
  record('ha_search', args);
  const query = (args.query || '').toLowerCase();
  const matches = inventory.entities.filter((entity) => {
    const area = areaNames.get(entity.area) || '';
    return (!query || `${entity.name} ${entity.id} ${area}`.toLowerCase().includes(query)) &&
      (!args.domain_filter || entity.id.startsWith(`${args.domain_filter}.`)) &&
      (!args.area_filter || area.toLowerCase() === args.area_filter.toLowerCase());
  }).map((entity) => ({ entity_id: entity.id, name: entity.name, area: areaNames.get(entity.area), state: String(entity.state ?? 'unknown') }));
  return result({ success: true, entities: matches, count: matches.length });
});

server.registerTool('ha_get_state', {
  description: 'Get current Home Assistant state and attributes for an entity ID or list of IDs. Read only.',
  annotations: annotation,
  inputSchema: {
    entity_id: z.union([z.string(), z.array(z.string()).max(100)]).describe('Entity ID or list of entity IDs'),
  },
}, async ({ entity_id }) => {
  record('ha_get_state', { entity_id });
  if (typeof entity_id === 'string') {
    const entity = byId.get(entity_id);
    return entity ? result({ data: stateRecord(entity), metadata: { time_zone: 'UTC' } }) :
      { isError: true, ...result({ success: false, error: 'Entity not found' }) };
  }
  const states = {};
  const errors = {};
  for (const id of new Set(entity_id)) {
    const entity = byId.get(id);
    if (entity) states[id] = stateRecord(entity);
    else errors[id] = 'Entity not found';
  }
  return result({ data: { success: Object.keys(states).length > 0, count: Object.keys(states).length, states, errors, error_count: Object.keys(errors).length }, metadata: { time_zone: 'UTC' } });
});

server.connect(new StdioServerTransport()).catch((error) => {
  console.error(`Synthetic MCP server failed: ${error.message}`);
  process.exitCode = 1;
});
