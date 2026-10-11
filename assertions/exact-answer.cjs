// Only data comparisons occur here. Provider output is never executed.
module.exports = (output, context) =>
  typeof output === 'string' &&
  output.trim().toLowerCase() === context.vars.expected.toLowerCase();
