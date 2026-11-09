import { defineConfig } from '@playwright/test';
import path from 'node:path';
export default defineConfig({
  testDir: path.resolve('tests/frontend'), testMatch: 'exec03-*.spec.mjs',
  timeout: 90000, workers: 1, retries: 0,
  outputDir: process.env.EXEC03_EVIDENCE + '/browser-output',
  reporter: [['list'], ['json', { outputFile: process.env.EXEC03_EVIDENCE + '/browser-results.json' }]],
  use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, locale: 'ru-RU',
    trace: 'off', screenshot: 'only-on-failure' },
});
