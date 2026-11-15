import test from 'node:test';
import assert from 'node:assert/strict';
import { createPathActionBudget, parsePathBudget, preparePathBrowser } from './path-action-budget.mjs';

test('bounded profile rejects missing, zero and malformed limits before any delegate', () => {
  for (const value of [undefined, '', '0', '-1', '1.2', 'NaN', 'Infinity']) {
    assert.throws(() => parsePathBudget({ bounded: true, actionLimit: value, visualLimit: 1 }), /INVALID_PATH_ACTION_LIMIT/);
  }
  let contexts = 0;
  const browser = { newContext: () => { contexts++; } };
  assert.throws(() => preparePathBrowser(browser, { P4K_PATH_BOUNDED: '1',
    P4K_PATH_ACTION_LIMIT: '0', P4K_PATH_VISUAL_LIMIT: '1' }), /INVALID_PATH_ACTION_LIMIT/);
  assert.equal(contexts, 0);
});

test('two contexts, reload and helper share one reserve-before-delegate counter', async () => {
  let calls = 0;
  const makePage = () => ({ goto: async () => { calls++; }, reload: async () => { calls++; },
    locator: () => ({ click: async () => { calls++; } }) });
  const raw = { newContext: async () => ({ newPage: async () => makePage() }) };
  const budget = createPathActionBudget({ actions: 3, visuals: 2 });
  const browser = budget.wrap(raw);
  const first = await (await browser.newContext()).newPage();
  const second = await (await browser.newContext()).newPage();
  const helper = async (page) => page.locator('#fixed').click();
  await first.goto('about:blank');
  await second.reload();
  await helper(first);
  assert.equal(calls, 3);
  assert.throws(() => second.locator('#fixed').click(), /PATH_BUDGET_EXCEEDED/);
  assert.equal(calls, 3);
  assert.deepEqual(budget.receipt().used, { actions: 3, visuals: 2 });
  assert.equal(budget.receipt().status, 'exceeded');
});

test('in-limit action succeeds; failed delegate still spends one unit', async () => {
  let calls = 0;
  const budget = createPathActionBudget({ actions: 2, visuals: 1 });
  const page = budget.wrap({ click: async () => { calls++; if (calls === 1) throw Error('delegate'); } });
  assert.equal(budget.wrap(page), page);
  await assert.rejects(page.click(), /delegate/);
  await page.click();
  budget.finish();
  assert.equal(calls, 2);
  assert.equal(budget.receipt().status, 'completed');
  assert.throws(() => page.click(), /PATH_BUDGET_EXCEEDED/);
  assert.equal(calls, 2);
});

test('visual N+1 is rejected before screenshot delegate', async () => {
  let screenshots = 0;
  const budget = createPathActionBudget({ actions: 1, visuals: 1 });
  const page = budget.wrap({ screenshot: async () => { screenshots++; } });
  await page.screenshot();
  assert.throws(() => page.screenshot(), /PATH_BUDGET_EXCEEDED/);
  assert.equal(screenshots, 1);
  assert.equal(budget.receipt().rejected.kind, 'visuals');
});
