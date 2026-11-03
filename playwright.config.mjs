import { defineConfig } from '@playwright/test';
const browserSuite=process.env.BROWSER_SUITE;
if(browserSuite && !['fast','runtime'].includes(browserSuite)) throw new Error(`Unknown BROWSER_SUITE: ${browserSuite}`);
export default defineConfig({testDir:'tests/browser',testMatch:browserSuite==='runtime'?'runtime.spec.mjs':'*.spec.mjs',
  testIgnore:browserSuite==='fast'?'runtime.spec.mjs':undefined,timeout:150000,workers:1,retries:0,
  outputDir:'.test-stand/browser-output',reporter:[['list'],['json',{outputFile:'.test-stand/browser-results.json'}]],
  use:{browserName:'chromium',viewport:{width:1440,height:1000},locale:'ru-RU',trace:'off',screenshot:'only-on-failure',acceptDownloads:true}});
