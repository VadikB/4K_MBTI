import assert from 'node:assert/strict';
import test from 'node:test';
import { state, safeStorage, STORAGE_KEYS, clearAssessmentContext, applyJourneyAssessmentContext } from '../../web/js/state.js';

test('ending an account context clears profile caches even before lazy UI cleanup', () => {
  state.pendingUser = {id: 1};
  state.profileSummary = {user: {id: 1}};
  state.profileAvatarDraft = 'synthetic-avatar';
  state.profileSkillsBySession = {11: ['private old result']};
  state.profileSkillAssessments = ['private old result'];
  safeStorage.setItem(STORAGE_KEYS.pendingUser, JSON.stringify(state.pendingUser));
  state.skillAssessments = ['old report'];
  state.assessmentSessionId = 11;
  state.reportReturnTarget = 'reports';
  const priorRequest = state.reportRequestEpoch;
  const prior = state.identityEpoch;
  clearAssessmentContext();
  assert.equal(state.pendingUser, null);
  assert.equal(state.profileSummary, null);
  assert.equal(state.profileAvatarDraft, null);
  assert.deepEqual(state.profileSkillsBySession, {});
  assert.deepEqual(state.profileSkillAssessments, []);
  assert.equal(safeStorage.getItem(STORAGE_KEYS.pendingUser), null);
  assert.ok(state.identityEpoch > prior);
  assert.ok(state.reportRequestEpoch > priorRequest);
  assert.deepEqual(state.skillAssessments, []);
  assert.equal(state.assessmentSessionId, null);
  assert.equal(state.reportReturnTarget, 'home');
});

test('server journey replaces and removes the complete runtime identity tuple', () => {
  applyJourneyAssessmentContext({assessment: {
    runtime_kind: 'cycle', cycle_id: 'cycle-new',
    assessment_situation_id: 'as-new',
  }});
  assert.equal(safeStorage.getItem(STORAGE_KEYS.productCycleId), 'cycle-new');
  assert.equal(safeStorage.getItem(STORAGE_KEYS.productAssessmentSituationId), 'as-new');

  applyJourneyAssessmentContext({assessment: {status: 'not_started'}});
  for (const key of [
    STORAGE_KEYS.assessmentSessionId,
    STORAGE_KEYS.assessmentSessionCode,
    STORAGE_KEYS.assessmentRuntimeKind,
    STORAGE_KEYS.productCycleId,
    STORAGE_KEYS.productAssessmentSituationId,
  ]) assert.equal(safeStorage.getItem(key), null);
});
