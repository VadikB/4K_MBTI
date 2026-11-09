import { defineConfig } from '@playwright/test';
import path from 'node:path';

export default defineConfig({
  testDir: path.resolve('tests/frontend'), testMatch: 'p3-a-chat-mobile.spec.mjs',
  timeout: 90000, workers: 1, retries: 0,
  outputDir: path.resolve('.test-stand/p3-a-browser-output'),
  reporter: [['list'], ['json', { outputFile: path.resolve('.test-stand/p3-a-browser-results.json') }]],
  use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, locale: 'ru-RU',
    trace: 'off', screenshot: 'only-on-failure' },
});
