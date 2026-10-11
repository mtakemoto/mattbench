// Offline smoke configuration. The fixture JSON remains the single task source.
const tasks = require('./tasks/smoke.json');

module.exports = {
  description: 'Two no-tool smoke cases (synthetic provider)',
  prompts: ['{{prompt}}'],
  providers: [
    { id: 'file://./providers/smoke-stub.cjs', label: 'Synthetic fixture stub' },
  ],
  tests: tasks.map((task) => ({
    description: task.id,
    metadata: { category: task.category },
    vars: { task_id: task.id, prompt: task.prompt, expected: task.expected },
    assert: [{ type: 'javascript', value: 'file://./assertions/exact-answer.cjs' }],
  })),
};
