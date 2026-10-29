import test from 'node:test';
import assert from 'node:assert/strict';
import { resumeOnboardingIndex, onboardingScopeKey, preparationView } from '../../web/js/onboarding-flow.js';

const model = (answers = {}, extra = {}) => ({
  readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic:a', questionnaire_revision_id: 1,
    briefing: { consent_version: 2, questions: ['Synthetic q1', 'Synthetic q2', 'Synthetic q3'] } },
  state: { consent_version: 2, consent_accepted_at: 'synthetic-accepted', answers_json: answers },
  mandatory_complete: false, ...extra,
});

test('resume uses actual consent and saved answers rather than legacy skipped/current_step', () => {
  assert.equal(resumeOnboardingIndex(model({}, { state: {} }), { status: 'skipped', current_step: 99 }), 1);
  assert.equal(resumeOnboardingIndex(model()), 2);
  assert.equal(resumeOnboardingIndex(model({ answer_1: 'Saved' })), 3);
  assert.equal(resumeOnboardingIndex(model({ answer_1: 'Saved', answer_2: 'Не знаю' })), 4);
  const all = model({ answer_1: 'A', answer_2: 'B', answer_3: 'C' });
  assert.equal(resumeOnboardingIndex(all, { status: 'skipped', current_step: 99 }), 5);
  all.mandatory_complete = true;
  assert.equal(resumeOnboardingIndex(all), 6);
  assert.equal(resumeOnboardingIndex(all, { current_step: 7 }), 7);
  assert.equal(resumeOnboardingIndex(all, { status: 'completed' }), 8);
});

test('local operation key separates account, tenant, assignment and questionnaire revision', () => {
  const original = model();
  const first = onboardingScopeKey(1, original);
  assert.notEqual(first, onboardingScopeKey(2, original));
  for (const [key, value] of [['organization_id', 20], ['assignment_ref', 'synthetic:b'], ['questionnaire_revision_id', 2]]) {
    assert.notEqual(first, onboardingScopeKey(1, { ...original, readiness: { ...original.readiness, [key]: value } }));
  }
});

test('readiness distinguishes organizational waiting, job status, network and admitted prepared plan', () => {
  const current = model();
  assert.equal(preparationView(current), 'organization');
  current.late_readiness = { status: 'ready_to_prepare' };
  assert.equal(preparationView(current), 'preparing');
  current.preparation_operation = { operation_id: 'synthetic-operation', status: 'failed' };
  assert.equal(preparationView(current), 'failed');
  assert.equal(preparationView(current, { kind: 'network' }), 'network');
  assert.equal(preparationView(current, { kind: 'access' }), 'access');
  assert.equal(preparationView(current, { kind: 'conflict' }), 'conflict');
  assert.equal(preparationView(current, { kind: 'service' }), 'service');
  current.preparation_operation.status = 'completed';
  assert.equal(preparationView(current), 'plan_missing');
  current.prepared_plan = { cycle_id: 'synthetic-cycle', plan: { route: [{}], time_budget_seconds: 1, calendar_window_seconds: 2 } };
  assert.equal(preparationView(current), 'ready');
  for (const status of ['queued', 'running', 'unknown']) {
    current.preparation_operation.status = status;
    assert.equal(preparationView(current), 'preparing');
  }
});
