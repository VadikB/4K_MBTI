// Explicit opt-in: renders the immutable standalone attachment in its own clean context.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { w02Layout } from './fixtures/w02-layout.mjs';
const input = process.env.W02_REFERENCE_HTML;
const evidence = process.env.W02_EVIDENCE_DIR;
const expectedSha = '2ae50fbe1ef73b4eb9fa6c808fec16d31475fb5cf79bb3d69ff275d41447170c';
const titles = { ready: 'Можно приступать к оценке', preparing: 'Готовим вашу оценку', 'failed-locked': 'Не удалось подготовить оценку', organization: 'Нужны сведения организации' };
for (const width of [1440, 390]) for (const scene of Object.keys(titles)) {
  test(`W02 ADD01 direct reference ${scene} ${width}`, async ({ browser }) => {
    test.skip(!input || !evidence, 'Requires the original W02 v5 attachment and an explicit evidence directory');
    const resolved = await fs.realpath(input), bytes = await fs.readFile(resolved);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(expectedSha);
    const context = await browser.newContext({ viewport: { width, height: width === 1440 ? 1024 : 844 }, deviceScaleFactor: 1, locale: 'ru-RU', serviceWorkers: 'block' });
    try {
      const page = await context.newPage(), requests = [];
      page.on('request', (req) => requests.push(req.url()));
      const url = pathToFileURL(resolved); url.hash = `stage=${scene}&show=1`;
      await page.goto(url.href);
      await page.evaluate(() => document.fonts.ready);
      await expect(page.locator('#app')).toHaveClass(/standalone/);
      await expect(page.locator('.status-title h1')).toHaveText(titles[scene]);
      await expect(page.locator('#section-name')).toHaveText('ОЦЕНКА');
      await expect(page.locator('#footer')).toBeVisible();
      await expect(page.locator('body')).not.toContainText(/Версия|2\.1\.10|2\.1\.11/);
      const runtime = await page.evaluate(() => ({ scripts: [...document.scripts].map((s) => s.src), css: [...document.querySelectorAll('link[rel="stylesheet"]')].map((s) => s.href), stage: JSON.parse(localStorage.getItem('lidum-w02-v5') || 'null') }));
      expect(runtime.scripts.filter(Boolean)).toEqual([]);
      expect(runtime.css).toEqual([]);
      expect(requests.filter((url) => /\/users\//.test(url))).toEqual([]);
      expect(requests.every((request) => request.startsWith('file:') || request.startsWith('data:'))).toBe(true);
      const target = path.join(evidence, `reference-${scene}-${width}.png`);
      await page.screenshot({ path: target, fullPage: false });
      const layout = await w02Layout(page, true);
      await fs.writeFile(target.replace('.png', '.json'), JSON.stringify({ input: resolved, input_sha256: expectedSha, input_bytes: bytes.length, scene, capture: { fullPage: false, deviceScaleFactor: 1, viewport: { width, height: width === 1440 ? 1024 : 844 }, waits: ['document.fonts.ready', 'actual standalone title', 'visible footer'], clean_context: true, DOM_or_style_injection: false }, requests, runtime, layout, png_sha256: createHash('sha256').update(await fs.readFile(target)).digest('hex') }, null, 2));
    } finally { await context.close(); }
  });
}
