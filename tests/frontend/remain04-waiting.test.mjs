import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');
const start = wiring.indexOf('if (authCompleteContinueButton) {');
const handler = wiring.slice(start, wiring.indexOf('\nif (authResendEmailButton)', start))
  .replaceAll("await import('./session.js')", 'sessionModule')
  .replaceAll("await import('./router.js')", 'routerModule');
const setup = (request) => {
  let click;
  const rendered = [];
  const button = { dataset: { action: 'check-acquaintance-readiness' }, disabled: false,
    addEventListener: (_event, fn) => { click = fn; } };
  const context = vm.createContext({
    authCompleteContinueButton: button,
    state: { pendingUser: { id: 1 }, identityEpoch: 0, currentScreen: 'auth-complete' },
    sessionModule: { loadUserJourneyState: request },
    routerModule: { openAcquaintanceWaiting: (value) => rendered.push(value) },
    window: { location: { reload: () => rendered.push('reload') } },
    withScreen: () => { throw Error('Unexpected legacy/management route'); }, loadChat: null,
  });
  vm.runInContext(handler, context);
  return { click, context, button, rendered };
};

test('actual waiting click remains waiting, handles refusal, and never opens legacy', async () => {
  const waiting = { status: 'waiting_for_assignment' };
  const run = setup(async () => ({ next_action: 'wait_for_acquaintance_data', acquaintance: { readiness: waiting } }));
  await run.click();
  assert.equal(run.rendered[0], waiting);
  assert.equal(run.button.disabled, false);
  const refused = setup(async () => { throw Error('synthetic network refusal'); });
  await refused.click();
  assert.equal(refused.rendered[0].title, 'Не удалось проверить готовность');
  assert.equal(refused.button.disabled, false);
});

test('actual waiting click ignores a late owner response and an obsolete screen', async () => {
  for (const change of ['owner', 'screen']) {
    let finish;
    const run = setup(() => new Promise((resolve) => { finish = resolve; }));
    const task = run.click();
    if (change === 'owner') { run.context.state.pendingUser.id = 2; run.context.state.identityEpoch++; }
    else run.context.state.currentScreen = 'auth';
    finish({ next_action: 'show_onboarding' });
    await task;
    assert.deepEqual(run.rendered, []);
  }
});

test('actual waiting click reconciles an assignment through server journey', async () => {
  const run = setup(async () => ({ next_action: 'show_onboarding' }));
  await run.click();
  assert.deepEqual(run.rendered, ['reload']);
});
