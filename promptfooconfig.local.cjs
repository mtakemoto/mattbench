const smoke = require('./promptfooconfig.cjs');
const { getLocalSettings } = require('./scripts/local-settings.cjs');

const { baseUrl, model } = getLocalSettings();

module.exports = {
  ...smoke,
  description: 'Two no-tool smoke cases (local OpenAI-compatible model)',
  providers: [{
    id: `openai:chat:${model}`,
    label: `Local FreeToken: ${model}`,
    config: {
      apiBaseUrl: baseUrl,
      apiKeyRequired: false,
      useDefaultApiKey: false,
      temperature: 0,
      max_tokens: 512,
      showThinking: false,
    },
  }],
};
