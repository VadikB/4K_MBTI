import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'tests/browser',testMatch:'*.spec.mjs',timeout:150000,workers:1,retries:0,
  outputDir:'.test-stand/browser-output',reporter:[['list'],['json',{outputFile:'.test-stand/browser-results.json'}]],
  use:{browserName:'chromium',viewport:{width:1440,height:1000},locale:'ru-RU',trace:'off',screenshot:'only-on-failure',acceptDownloads:true}});
