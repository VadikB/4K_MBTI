import path from 'node:path';
import { defineConfig } from '@playwright/test';
import baseConfig from '../../playwright.config.mjs';

const browserSuite = process.env.BROWSER_SUITE;
if (!['fast', 'runtime'].includes(browserSuite)) {
  throw new Error(`BROWSER_SUITE must be fast or runtime, got: ${browserSuite || '<empty>'}`);
}

export default defineConfig({
  ...baseConfig,
  testDir: path.resolve(process.cwd(), 'tests/browser'),
  testMatch: browserSuite === 'runtime' ? 'runtime.spec.mjs' : '*.spec.mjs',
  testIgnore: browserSuite === 'fast' ? 'runtime.spec.mjs' : undefined,
});
