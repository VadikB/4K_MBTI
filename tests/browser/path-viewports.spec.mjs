// Collector-only DOM regressions, NOT product/HTTP/admission evidence.
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { capturePathViewports, viewportGeometry, assertViewportGeometry } from './fixtures/path-viewports.mjs';

test('viewport collector measures final scroll geometry on active tab without clicks or enabling controls', async ({ browser }, testInfo) => {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.setContent(`<style>body{margin:0}button{width:200px;height:48px}</style>
      <div style="height:2200px">synthetic collector fixture</div>
      <button id="enabled" onclick="document.body.dataset.clicked='yes'">enabled</button>
      <button id="disabled" disabled>disabled</button>`);
    const other = await context.newPage();
    await other.setContent('<p>other tab</p>');
    const directory = testInfo.outputPath('viewports');
    fs.mkdirSync(directory, { recursive: true });
    const initial = page.viewportSize();
    const records = await capturePathViewports(page, directory, 'collector', [
      { name: 'enabled', locator: page.locator('#enabled') },
      { name: 'disabled', locator: page.locator('#disabled') },
    ]);
    expect(records.map((r) => r.width)).toEqual([1440, 320, 390, 768]);
    for (const record of records) {
      expect(fs.existsSync(path.join(directory, record.screenshot))).toBe(true);
      for (const control of record.controls) {
        expect(control.geometry.visible_ratio).toBeGreaterThan(0);
        expect(control.geometry.visibility).toBe('visible');
      }
    }
    expect(page.viewportSize()).toEqual(initial);
    await expect(page.locator('#disabled')).toBeDisabled();
    expect(await page.locator('body').getAttribute('data-clicked')).toBeNull();
  } finally { await context.close(); }
});

test('viewport geometry rejects offscreen, ancestor clipping and horizontal overflow', async ({ page }) => {
  await page.setContent(`<style>body{margin:0}button{width:100px;height:40px}</style>
    <div style="width:120px;height:20px;overflow:hidden">
      <button id="clipped" style="transform:translateY(60px)">clipped</button></div>
    <button id="offscreen" style="position:absolute;top:2200px">offscreen</button>
    <button id="overflow" style="position:fixed;right:-50px;top:200px">overflow</button>
    <button id="visible" style="position:fixed;left:10px;top:300px">visible</button>`);
  for (const id of ['clipped', 'offscreen', 'overflow']) {
    const geometry = await viewportGeometry(page.locator('#' + id));
    expect(() => assertViewportGeometry(geometry, id)).toThrow();
  }
  assertViewportGeometry(await viewportGeometry(page.locator('#visible')), 'visible');
});
