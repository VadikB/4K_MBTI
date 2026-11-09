// Static HTML/CSS comparison only. Auth/runtime/turn HTTP stays real main.app+PG.
import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = process.env.P3_A_BASE || 'http://127.0.0.1:18931';
const directory = process.env.P3_A_EVIDENCE || '.test-stand/p3-a-baseline';
const revision = process.env.P3_A_BASE_SHA || '023bf85ec796d212d29b33218d906a1ed2023941';
if (!/^[a-f0-9]{40}$/.test(revision)) throw new Error('Exact baseline SHA required');
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base)) throw new Error('Owned localhost origin required');
fs.mkdirSync(directory, { recursive: true });
const previous = (file) => execFileSync('git', ['show', `${revision}:${file}`]);
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, locale: 'ru-RU' });
  await page.route('**/*', (route) => {
    const url = new URL(route.request().url());
    if (url.origin === base && url.pathname === '/') return route.fulfill({
      contentType: 'text/html', body: previous('web/index.html') });
    if (url.origin === base && url.pathname === '/web/styles/screens/interview.css') return route.fulfill({
      contentType: 'text/css', body: previous('web/styles/screens/interview.css') });
    return route.continue();
  });
  await page.goto(`${base}/p3-a/open/long`);
  await page.locator('.interview-message--situation').waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
  for (const phase of ['before', 'after']) {
    if (phase === 'after') {
      await page.unroute('**/*');
      await page.reload();
      await page.locator('.interview-message--situation').waitFor();
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(400);
    }
    const metrics = await page.evaluate(() => {
      const measure = (id) => {
        const element = document.getElementById(id), rect = element.getBoundingClientRect();
        return { top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height,
          scrollTop: element.scrollTop, scrollHeight: element.scrollHeight, clientHeight: element.clientHeight };
      };
      return { viewport: { width: innerWidth, height: innerHeight },
        document: { scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight },
        input: measure('interview-textarea'), submit: measure('interview-submit-button'),
        history: measure('interview-scroll-area') };
    });
    fs.writeFileSync(path.join(directory, `${phase}-390.json`), JSON.stringify({
      baseline_sha: revision, phase, scope: 'static HTML/CSS only; unchanged real auth/runtime/PG', ...metrics }, null, 2) + '\n');
    await page.screenshot({ path: path.join(directory, `${phase}-390.png`), fullPage: false });
    console.log(JSON.stringify({ phase, ...metrics }));
  }
} finally { await browser.close(); }
