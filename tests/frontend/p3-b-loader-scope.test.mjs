import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

// Execute the production read paths with deferred synthetic responses. No DB,
// network or DOM is involved; browser/HTTP checks cover the integrated UI.
const source = fs.readFileSync(new URL('../../web/js/screens/interview.js', import.meta.url), 'utf8');
const section = (start, end) => {
  const from = source.indexOf(start);
  const to = source.indexOf(end, from);
  assert.ok(from >= 0 && to > from, `source section ${start}`);
  return source.slice(from, to).replace(/^export const /, 'const ');
};
const runtimeSource = section('export const loadProductRuntime =', '\nconst waitForProductClarification =');
const returnSource = section('const loadReturnState =', '\nexport const loadProductRuntime =');

const deferred = () => {
  let resolve;
  const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
};
const snapshot = (assessmentSituationId = 'as-A', returnPolicy = false) => ({
  cycle_id: 'cycle-A',
  current_situation: { assessment_situation_id: assessmentSituationId, status: 'active' },
  status: { collection_status: 'active' }, return_policy_enabled: returnPolicy,
});
const harness = ({ actualReturnState = false, presence = null } = {}) => {
  const state = { currentScreen: 'interview', productCycleId: 'cycle-A',
    productAssessmentSituationId: 'as-A', pendingUser: { id: 1 }, identityEpoch: 1 };
  const requested = deferred();
  const response = deferred();
  const renders = [];
  const cards = [];
  const effects = [];
  let viewGeneration = 0;
  const context = vm.createContext({
    state, encodeURIComponent,
    getAssessmentViewGeneration: () => viewGeneration,
    advanceAssessmentViewGeneration: () => { viewGeneration += 1; },
    fetch: (url) => { requested.resolve(url); return response.promise; },
    fetchWithDeadline: (url) => { requested.resolve(url); return response.promise; },
    readApiResponse: async (value) => value.syntheticPayload,
    renderReturnCard: (value) => cards.push(value),
    clearConfirmedReturnContinue: () => effects.push('clearContinue'),
    heartbeatProductPresence: presence || (async () => ({ heartbeat_interval_seconds: 30 })),
    renderProductRuntime: (value) => { renders.push(value); return value; },
    startProductPresence: () => effects.push('startPresence'),
    stopProductPresence: () => effects.push('stopPresence'),
    interviewPanel: { classList: { contains: () => true } },
    openProcessing: () => effects.push('openProcessing'),
  });
  vm.runInContext(`let productRuntimePollGeneration = 7; let returnPresenceCycleId = null;
    ${actualReturnState ? returnSource : 'const loadReturnState = async () => false;'}
    ${runtimeSource}
    globalThis.subject = { loadProductRuntime, loadReturnState,
      advanceGeneration: () => { productRuntimePollGeneration += 1; },
      advanceViewGeneration: advanceAssessmentViewGeneration };`, context);
  return { state, context, requested: requested.promise, resolve: response.resolve,
    renders, cards, effects, subject: context.subject };
};

test('P3-A+3B loader rejects late runtime for another owner, Cycle, AS or screen', async () => {
  const changes = [
    (h) => { h.state.pendingUser = { id: 2 }; h.state.identityEpoch += 1; },
    (h) => { h.state.productCycleId = 'cycle-B'; h.state.productAssessmentSituationId = 'as-B'; },
    (h) => { h.state.productAssessmentSituationId = 'as-B'; },
    (h) => { h.state.currentScreen = 'prechat'; },
    (h) => { h.subject.advanceGeneration(); },
    (h) => { h.subject.advanceViewGeneration(); },
  ];
  for (const change of changes) {
    const h = harness();
    const loading = h.subject.loadProductRuntime({ generation: 7 });
    assert.match(await h.requested, /cycle-A\/runtime$/);
    change(h);
    const expected = { cycle: h.state.productCycleId, situation: h.state.productAssessmentSituationId };
    h.resolve({ syntheticPayload: snapshot() });
    assert.equal(await loading, null);
    assert.equal(h.state.productCycleId, expected.cycle);
    assert.equal(h.state.productAssessmentSituationId, expected.situation);
    assert.equal(h.renders.length, 0);
    assert.deepEqual(h.effects, []);
  }
});

test('P3-A+3B default initial/visibility load rejects old AS but accepts server advance', async () => {
  const stale = harness();
  const loading = stale.subject.loadProductRuntime();
  await stale.requested;
  stale.state.productAssessmentSituationId = 'as-B';
  stale.resolve({ syntheticPayload: snapshot() });
  assert.equal(await loading, null);
  assert.equal(stale.state.productAssessmentSituationId, 'as-B');
  assert.equal(stale.renders.length, 0);

  const current = harness();
  const advancing = current.subject.loadProductRuntime();
  await current.requested;
  current.resolve({ syntheticPayload: snapshot('as-B') });
  assert.equal((await advancing).current_situation.assessment_situation_id, 'as-B');
  assert.equal(current.state.productAssessmentSituationId, 'as-B');
  assert.equal(current.renders.length, 1);
});

test('P3-A+3B late presence cannot apply effects after an AS replacement', async () => {
  const heartbeat = deferred();
  const heartbeatStarted = deferred();
  const h = harness({ presence: () => { heartbeatStarted.resolve(); return heartbeat.promise; } });
  const loading = h.subject.loadProductRuntime();
  await h.requested;
  h.resolve({ syntheticPayload: snapshot('as-B', true) });
  await heartbeatStarted.promise;
  assert.equal(h.renders.length, 1); // Confirmed runtime renders before the independent heartbeat.
  h.state.productAssessmentSituationId = 'as-C';
  heartbeat.resolve({ heartbeat_interval_seconds: 30 });
  assert.equal(await loading, null);
  assert.equal(h.state.productAssessmentSituationId, 'as-C');
  assert.equal(h.renders.length, 1); // The late heartbeat never renders again.
  assert.equal(h.effects.includes('startPresence'), false);
});

test('P3-A+3B delayed return-state cannot replace a newer AS card', async () => {
  const h = harness({ actualReturnState: true });
  const loading = h.subject.loadReturnState();
  assert.match(await h.requested, /cycle-A\/return-state$/);
  h.state.productAssessmentSituationId = 'as-B';
  h.resolve({ syntheticPayload: { cycle_id: 'cycle-A', allowed_action: 'continue_current' } });
  assert.equal(await loading, false);
  assert.equal(h.cards.length, 0);
});
