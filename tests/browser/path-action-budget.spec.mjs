import { test, expect } from '@playwright/test';
import { preparePathBrowser } from './fixtures/path-action-budget.mjs';

test('native browser reserves action and visual units before delegate', async ({ browser }) => {
  test.setTimeout(30000);
  const guarded = preparePathBrowser(browser, { P4K_PATH_BOUNDED: '1',
    P4K_PATH_ACTION_LIMIT: '2', P4K_PATH_VISUAL_LIMIT: '3' });
  const { budget } = guarded;
  const context = await guarded.browser.newContext();
  try {
    const page = await context.newPage();
    await page.setContent('<button id="go" onclick="this.dataset.count=(Number(this.dataset.count||0)+1)">Go</button>');
    await page.setViewportSize({ width: 800, height: 600 });
    await page.screenshot();
    await expect(page.locator('#go')).toBeVisible();
    await page.locator('#go').click();
    expect(await page.locator('#go').getAttribute('data-count')).toBe('1');
    expect(() => page.locator('#go').click()).toThrow('PATH_BUDGET_EXCEEDED');
    expect(() => page.bringToFront()).toThrow('PATH_BUDGET_EXCEEDED');
    expect(await page.locator('#go').getAttribute('data-count')).toBe('1');
    expect(budget.receipt()).toMatchObject({ status: 'exceeded', used: { actions: 2, visuals: 3 },
      rejected: { kind: 'actions', operation: 'click' } });
  } finally {
    await context.close();
  }
});
