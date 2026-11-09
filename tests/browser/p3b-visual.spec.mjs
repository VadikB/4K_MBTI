import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createP3BVisualServer } from '../../scripts/p3b_visual_preview.mjs';

let server;
let base;
const evidence = path.resolve('.test-stand/p3-b-visual');

test.beforeAll(async () => {
  server = createP3BVisualServer();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  await fs.mkdir(evidence, { recursive: true });
});

test.afterAll(async () => {
  await new Promise((resolve) => server.close(resolve));
});

test('P3-B synthetic visual states, progress and Continue are reproducible', async ({ browser }) => {
  const records = [];
  for (const mode of ['active-long', 'active-short', 'pause', 'return', 'unknown', 'recovered']) {
    for (const width of [1440, 768, 390, 320]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, locale: 'ru-RU' });
      const page = await context.newPage();
      await page.request.get(`${base}/p3b-reset`);
      await page.goto(`${base}/?screen=interview&p3b=${mode}`);
      const card = page.locator('.interview-return-card');
      if (['pause', 'return', 'unknown'].includes(mode)) {
        await expect(card).toBeVisible();
        await expect(page.locator('#interview-case-badge')).toHaveText(
          mode === 'pause' ? 'Ситуация 3 из 8' : 'Ситуация 1 из 8');
        await expect(card).toContainText(mode === 'pause' ? 'Завершено 2 из 8' : 'Завершено 0 из 8');
        await expect(page.locator('#interview-timer-badge')).toContainText('Пауза');
      } else {
        await expect(page.locator('#interview-case-badge')).toHaveText(
          mode === 'active-short' ? 'Ситуация 2 из 5' : 'Ситуация 1 из 8');
        await expect(page.locator('.interview-message--situation')).toBeVisible();
      }
      if (mode === 'unknown') {
        await expect(card).toContainText('Остаток времени выполнения уточняется');
        if (width === 390) {
          await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
          await expect(card).toContainText('Результат пока неизвестен');
          const keyBeforeReload = await page.evaluate(() => JSON.parse(sessionStorage.getItem('agent4k.returnContinuePending')).key);
          await page.reload();
          await expect(card).toBeVisible();
          const keyAfterReload = await page.evaluate(() => JSON.parse(sessionStorage.getItem('agent4k.returnContinuePending')).key);
          expect(keyAfterReload).toBe(keyBeforeReload);
        }
      }
      if (mode === 'return' && width === 390) {
        await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
        await expect(page.locator('.interview-message--situation')).toBeVisible();
        await expect(page.locator('.interview-message.own')).toContainText('Сначала уточню зависимость');
        await page.reload();
        await expect(page.locator('.interview-message.own')).toContainText('Сначала уточню зависимость');
      }
      const geometry = await page.evaluate(() => ({ documentWidth: document.documentElement.scrollWidth,
        viewportWidth: window.innerWidth }));
      expect(geometry.documentWidth, `${mode} ${width}px horizontal overflow`).toBeLessThanOrEqual(geometry.viewportWidth + 1);
      await page.screenshot({ path: path.join(evidence, `${mode}-${width}.png`), fullPage: true });
      records.push({ mode, viewport: width, result: 'PASS', screenshot: `${mode}-${width}.png` });
      if (mode === 'active-long' && width === 390) {
        await page.evaluate(() => {
          const nodes = [...document.querySelectorAll('.interview-panel, .interview-panel *')];
          const metrics = nodes.map((node) => ({ node, font: parseFloat(getComputedStyle(node).fontSize),
            line: parseFloat(getComputedStyle(node).lineHeight) }));
          metrics.forEach(({ node, font, line }) => {
            if (font > 0) node.style.fontSize = `${font * 2}px`;
            if (Number.isFinite(line)) node.style.lineHeight = `${line * 2}px`;
          });
        });
        const text200 = await page.evaluate(() => ({ documentWidth: document.documentElement.scrollWidth,
          viewportWidth: window.innerWidth,
          offenders: [...document.querySelectorAll('.interview-panel *')].filter((node) =>
            node.getBoundingClientRect().right > window.innerWidth + 1).slice(0, 8).map((node) =>
            ({ tag: node.tagName, className: node.className, width: node.getBoundingClientRect().width,
              right: node.getBoundingClientRect().right })) }));
        await page.screenshot({ path: path.join(evidence, 'active-long-390-text200.png'), fullPage: true });
        records.push({ mode, viewport: 390, text: '200% computed metrics emulation',
          result: text200.documentWidth <= text200.viewportWidth + 1 ? 'PASS' : 'FAIL',
          geometry: text200, screenshot: 'active-long-390-text200.png' });
      }
      await context.close();
    }
  }
  await fs.writeFile(path.join(evidence, 'manifest.json'), JSON.stringify({ base, records }, null, 2));
});
