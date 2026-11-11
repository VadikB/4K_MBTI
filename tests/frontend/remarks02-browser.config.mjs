import { defineConfig } from '@playwright/test';
import path from 'node:path';
const output = process.env.REMARKS02_CHAT_EVIDENCE || path.resolve('.test-stand/remarks02-chat');
export default defineConfig({
  testDir: path.resolve('tests/frontend'), testMatch: 'remarks02-assessment-errors.spec.mjs',
  timeout: 60000, workers: 1, retries: 0, outputDir: path.join(output, 'browser-output'),
  reporter: [['list'], ['json', { outputFile: path.join(output, 'browser-results.json') }]],
  use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, locale: 'ru-RU', trace: 'off', screenshot: 'only-on-failure' },
});
