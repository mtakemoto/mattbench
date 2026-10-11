const tasks = require('./tasks/ha-readonly.json');
const { getLocalSettings } = require('./scripts/local-settings.cjs');
const { model } = getLocalSettings();

module.exports = {
  description: 'One read-only synthetic Home Assistant MCP task (local model)',
  prompts: ['{{prompt}}'],
  providers: [{
    id: 'file://./providers/ha-local-agent.cjs',
    label: `Local FreeToken + synthetic HA MCP: ${model}`,
  }],
  tests: tasks.map((task) => ({
    description: task.id,
    metadata: { category: task.category, fixture: 'fixtures/ha/north-room.yaml' },
    vars: { prompt: task.prompt, expected: task.expected, required_entity_id: task.required_entity_id },
    assert: [{ type: 'javascript', value: 'file://./assertions/ha-readonly.cjs' }],
  })),
};
