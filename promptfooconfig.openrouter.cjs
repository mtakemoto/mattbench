const smoke = require('./promptfooconfig.cjs');

module.exports = {
  ...smoke,
  description: 'Two no-tool smoke cases (OpenRouter GLM 5.3 Flash)',
  providers: [{
    id: 'openrouter:z-ai/glm-5.3-flash',
    label: 'GLM 5.3 Flash via OpenRouter',
    // OpenRouter can return reasoning separately. Score only message.content.
    config: { temperature: 0, max_tokens: 512, showThinking: false },
  }],
};
