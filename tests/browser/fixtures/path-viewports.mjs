// Read-only presentation evidence. No request, start, answer or generation here.
import { expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

export async function capturePathViewports(page, directory, phase, controls) {
  const original = page.viewportSize();
  const records = [];
  const receipt = path.join(directory, `${phase}-viewports.json`);
  try {
    // PATH has other tabs/contexts. Observe layout on the user's active page;
    // background-tab IntersectionObserver delivery may be throttled by Chromium.
    await page.bringToFront();
    for (const width of [1440, 320, 390, 768]) {
      await page.setViewportSize({ width, height: 1000 });
      const record = { width, height: 1000, controls: [] };
      records.push(record);
      for (const { name, locator } of controls) {
        await expect(locator).toBeVisible();
        await locator.scrollIntoViewIfNeeded();
        const box = await locator.boundingBox();
        const enabled = await locator.isEnabled();
        const ancestors = await locator.evaluate((el) => {
          const values = [];
          for (let node = el; node && values.length < 8; node = node.parentElement) {
            const style = getComputedStyle(node), rect = node.getBoundingClientRect();
            values.push({ tag: node.tagName, id: node.id, position: style.position,
              overflowY: style.overflowY, y: rect.y, height: rect.height, scrollTop: node.scrollTop,
              clientHeight: node.clientHeight, scrollHeight: node.scrollHeight });
          }
          return values;
        });
        record.controls.push({ name, box, enabled, ancestors });
        fs.writeFileSync(receipt, JSON.stringify(records, null, 2) + '\n');
        // Trial performs the real pointer actionability checks but never clicks.
        // A disabled pre-answer finish/submit is expected, not forced enabled.
        if (enabled) await locator.click({ trial: true });
        await expect(locator).toBeInViewport();
        expect(box.x, `${phase}/${name}/${width}: left`).toBeGreaterThanOrEqual(-1);
        expect(box.x + box.width, `${phase}/${name}/${width}: right`).toBeLessThanOrEqual(width + 1);
      }
      record.document = await page.evaluate(() => ({
        viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth,
        visibleTextLength: document.body.innerText.length,
        visibility: document.visibilityState,
      }));
      record.screenshot = `${phase}-${width}.png`;
      fs.writeFileSync(receipt, JSON.stringify(records, null, 2) + '\n');
      await page.screenshot({ path: path.join(directory, record.screenshot), fullPage: true });
      expect(record.document.scrollWidth, `${phase}/${width}: document overflow`).toBeLessThanOrEqual(width + 1);
      expect(record.document.visibility).toBe('visible');
    }
  } catch (error) {
    const failed = records.at(-1);
    if (failed) {
      failed.error = 'VIEWPORT_ASSERTION_FAILED';
      fs.writeFileSync(receipt, JSON.stringify(records, null, 2) + '\n');
      await page.screenshot({ path: path.join(directory, `${phase}-failed-${failed.width}.png`), fullPage: true });
    }
    throw error;
  } finally {
    if (original) await page.setViewportSize(original);
  }
  return records;
}
