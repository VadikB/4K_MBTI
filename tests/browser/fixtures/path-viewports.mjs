// Read-only presentation evidence. No request, start, answer or generation here.
import { expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

// Read current geometry AFTER Playwright's trial scroll. Account for each
// clipping ancestor, not only getBoundingClientRect() or a stale IO callback.
export async function viewportGeometry(locator) {
  return locator.evaluate((el) => {
    const rect = el.getBoundingClientRect();
    let left = Math.max(0, rect.left), right = Math.min(innerWidth, rect.right);
    let top = Math.max(0, rect.top), bottom = Math.min(innerHeight, rect.bottom);
    for (let parent = el.parentElement; parent; parent = parent.parentElement) {
      const style = getComputedStyle(parent), r = parent.getBoundingClientRect();
      if (/^(auto|scroll|hidden|clip)$/.test(style.overflowX)) {
        left = Math.max(left, r.left + parent.clientLeft);
        right = Math.min(right, r.left + parent.clientLeft + parent.clientWidth);
      }
      if (/^(auto|scroll|hidden|clip)$/.test(style.overflowY)) {
        top = Math.max(top, r.top + parent.clientTop);
        bottom = Math.min(bottom, r.top + parent.clientTop + parent.clientHeight);
      }
    }
    const area = Math.max(0, right - left) * Math.max(0, bottom - top);
    return { box: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
      viewport: { width: innerWidth, height: innerHeight },
      clipped: { left, right, top, bottom }, visible_area: area,
      visible_ratio: rect.width * rect.height > 0 ? area / (rect.width * rect.height) : 0,
      visibility: document.visibilityState };
  });
}

export function assertViewportGeometry(geometry, label) {
  expect(geometry.visibility, `${label}: active page`).toBe('visible');
  expect(geometry.visible_ratio, `${label}: clipped viewport intersection`).toBeGreaterThan(0);
  expect(geometry.box.x, `${label}: left`).toBeGreaterThanOrEqual(-1);
  expect(geometry.box.x + geometry.box.width, `${label}: right`)
    .toBeLessThanOrEqual(geometry.viewport.width + 1);
}

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
        const enabled = await locator.isEnabled();
        const control = { name, enabled };
        record.controls.push(control);
        // Trial performs pointer actionability but never clicks. Preserve disabled
        // controls: do not force-enable them just to collect evidence.
        if (enabled) await locator.click({ trial: true });
        const geometry = await viewportGeometry(locator);
        Object.assign(control, { box: geometry.box, geometry });
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
        control.ancestors = ancestors;
        fs.writeFileSync(receipt, JSON.stringify(records, null, 2) + '\n');
        assertViewportGeometry(geometry, `${phase}/${name}/${width}`);
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
