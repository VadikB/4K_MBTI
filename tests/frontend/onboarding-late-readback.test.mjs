import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { onboardingScopeKey } from '../../web/js/onboarding-flow.js';

const source = readFileSync('web/js/screens/onboarding.js', 'utf8');
const start = source.indexOf('const loadAcquaintance = async () => {');
const end = source.indexOf('\nconst saveProgress =', start);
const handler = source.slice(start, end);

const deferred = () => {
  let resolve;
  const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
};

test('late acquaintance GET cannot replace a newer assignment generation', async () => {
  const old = deferred(), current = deferred();
  const requests = [old.promise, current.promise];
  const storage = new Map();
  const context = vm.createContext({
    acquaintanceRequest: 0, scopeKey: '', generation: 1,
    state: { identityEpoch: 1 }, model: null, savedAnswers: {}, answers: {},
    loadFailed: false, localOperation: null, draftKeys: new Set(),
    identity: () => '99', isCurrent: () => true, onboardingScopeKey,
    api: () => requests.shift(), draftKey: () => 'draft', operationKey: () => 'operation',
    readDraft: () => ({}), window: { sessionStorage: {
      getItem: (key) => storage.get(key) || null,
      removeItem: (key) => storage.delete(key),
    } },
  });
  vm.runInContext(`${handler}\nglobalThis.load = loadAcquaintance;`, context);
  const response = (assignment_id) => ({
    assignment_id, mandatory_complete: true,
    readiness: { organization_id: 10, assignment_ref: 'same-ref', questionnaire_revision_id: 21 },
    late_readiness: { personalized_profile_id: 7 }, state: { answers_json: {} },
  });
  const pendingOld = context.load();
  const pendingCurrent = context.load();
  current.resolve(response(42));
  await pendingCurrent;
  old.resolve(response(41));
  await assert.rejects(pendingOld, (error) => error.name === 'PreparationWaitStopped');
  assert.equal(context.model.assignment_id, 42);
  assert.equal(context.scopeKey, onboardingScopeKey('99', response(42)));
});
