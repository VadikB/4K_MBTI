import assert from 'node:assert/strict';
import test from 'node:test';
import { state, safeStorage, STORAGE_KEYS, clearAssessmentContext } from '../../web/js/state.js';

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
