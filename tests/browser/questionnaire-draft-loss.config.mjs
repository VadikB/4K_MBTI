import { defineConfig } from '@playwright/test';

// Explicit diagnostic command only. Never a green product/AC18 acceptance gate.
export default defineConfig({
  testDir: '.', testMatch: 'questionnaire-draft-loss.diagnostic.mjs',
  timeout: 150000, workers: 1, retries: 0,
  outputDir: '../../.test-stand/questionnaire-draft-diagnostic-output',
  reporter: [['list'], ['json', { outputFile: '.test-stand/questionnaire-draft-diagnostic-results.json' }]],
  use: { browserName: 'chromium', viewport: { width: 1440, height: 1000 },
    locale: 'ru-RU', trace: 'off', screenshot: 'off' },
});
