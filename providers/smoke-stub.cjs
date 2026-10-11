// Deterministic transport fixture. This does not call a model or Home Assistant.
const answers = Object.freeze({
  strawberry_r_count: '3',
  car_wash_transport: 'DRIVE',
});

module.exports = class SmokeStub {
  id() {
    return 'synthetic:smoke-stub';
  }

  async callApi(_prompt, context) {
    const output = answers[context.vars.task_id];
    return output === undefined
      ? { error: `Unknown smoke task: ${context.vars.task_id}` }
      : { output };
  }
};
