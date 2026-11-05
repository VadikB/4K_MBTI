// Explicit opt-in only; default acceptance configuration is unchanged.
export default {
  testDir: '../../../../tests/browser',
  testMatch: 'auth-recovery-race.diagnostic.mjs',
  timeout: 30000, workers: 1, retries: 0,
  outputDir: '../../../../.test-stand/auth-diagnostic-output',
  reporter: [['list'], ['json', { outputFile: '.test-stand/auth-diagnostic-results.json' }]],
  use: { browserName: 'chromium', viewport: { width: 1440, height: 1000 }, locale: 'ru-RU', trace: 'off', screenshot: 'only-on-failure' },
};
