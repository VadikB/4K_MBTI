import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../../web/js/screens/admin/organizations.js', import.meta.url), 'utf8');
const wiring = readFileSync(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');
const entry = readFileSync(new URL('../../web/js/entries/admin-organizations.js', import.meta.url), 'utf8');

test('R10 feedback rehydrates only the exact current identity, organization, selection and connection', () => {
  const restore = source.match(/const restoreProgramConnectionFeedback[\s\S]*?\n\};/)?.[0] || '';
  for (const guard of ['outcome.identityEpoch !== state.identityEpoch', 'outcome.identityKey !== currentIdentityKey()',
    'Number(selectedOrganizationId) !== outcome.organizationId', 'outcome.programDefinitionId',
    'outcome.connectedProgramDefinitionId']) assert.ok(restore.includes(guard), guard);
  assert.match(source, /restoreAdminOrganizationsDraft\(\);\s*restoreProgramConnectionFeedback\(\)/);
  assert.match(restore, /setLocalOperationStatus\(form, outcome.message, outcome.tone\)/);
  assert.doesNotMatch(restore, /setStatus\(/);
});

test('R10 late feedback is generation guarded while exact server readback stays mandatory', () => {
  const connect = source.match(/export const connectAdminOrganizationProgram[\s\S]*?\n\};/)?.[0] || '';
  assert.match(connect, /feedbackGeneration !== programConnectionFeedbackGeneration/);
  assert.match(connect, /identityEpoch !== state.identityEpoch/);
  assert.match(connect, /setStatus\(message, tone, form\)/);
  assert.match(connect, /isExactProgramConnection\(commandConnection, organizationId, programDefinitionId\)/);
  assert.match(connect, /isExactProgramConnection\(readback, organizationId, programDefinitionId\)/);
  assert.doesNotMatch(connect, /safeStorage\.setItem.*programConnectionOutcome/);
});

test('R10 feedback is invalidated on session clearing, selection and new actions', () => {
  assert.match(source, /programConnectionOperationIds.clear\(\);\s*programConnectionOutcome = null;\s*programConnectionFeedbackGeneration \+= 1/);
  assert.match(source, /export const selectAdminOrganization = [\s\S]*?clearProgramConnectionFeedback\(\)/);
  assert.match(source, /const trackOperation = [\s\S]*?clearProgramConnectionFeedback\(\)/);
  assert.match(source, /select\[name="program_definition_id"\][\s\S]*?clearProgramConnectionFeedback\(\)/);
});

test('ARCH30 connects an exact published program version from the superadmin UI', () => {
  assert.match(source, /assessment_programs/);
  assert.match(source, /program_definition_id/);
  assert.match(source, /createOperationId\(\)/);
  assert.match(source, /\/assessment-program/);
  assert.match(wiring, /connect-assessment-program/);
  assert.match(wiring, /connectAdminOrganizationProgram/);
  assert.match(entry, /connectAdminOrganizationProgram/);
  assert.match(source, /roleCapabilities\.length/);
  assert.match(source, /role_capabilities/);
  assert.match(source, /unavailable_reason/);
  assert.match(source, /commandConnection/);
  assert.match(source, /readback/);
  assert.match(source, /readAdminOrganizationProgram/);
  assert.match(source, /\/assessment-program', \{\s*method: 'GET'/);
  assert.match(source, /refreshAdminOrganizationQuestionnaireInBackground/);
  assert.doesNotMatch(
    source.match(/export const connectAdminOrganizationProgram[\s\S]*?\n\};/)?.[0] || '',
    /await loadAdminOrganizations\(\)/,
  );
});

test('PROGRAM01 rejects incomplete assignment batches and preserves role-scoped idempotency', () => {
  assert.match(source, /responseMatchesRequest/);
  assert.match(source, /неполный или противоречивый результат назначения/);
  assert.match(source, /':role:'/);
  assert.doesNotMatch(source, /Оценка для специалистов назначена со всеми проверенными источниками/);
});

test('PROGRAM01 restores the bulk selection projection and rejects stale organization reads', () => {
  assert.match(source, /syncParticipantSelection\(card\)/);
  assert.match(source, /organizationsRequestGeneration/);
  assert.match(source, /requestGeneration !== organizationsRequestGeneration/);
});

test('PROGRAM01 R06 scopes cancellation and exposes stale readback recovery', () => {
  const cancellation = source.match(/export const cancelAdminOrganizationAssessment[\s\S]*?\n\};/)?.[0] || '';
  assert.match(cancellation, /identityEpoch/);
  assert.match(cancellation, /identityKey/);
  assert.match(cancellation, /assessmentRef/);
  assert.match(cancellation, /cancellationRequestsInFlight/);
  assert.match(cancellation, /refreshExactAssignment/);
  assert.match(cancellation, /readback\?\.code === 'cancelled'/);
  assert.match(cancellation, /Number\(error\?\.status\) === 409/);
  assert.match(cancellation, /restoreButton\(\)/);
  assert.match(source, /data-organizations-stale/);
  assert.match(source, /refreshAdminOrganizationsSafely/);
  assert.match(entry, /refreshAdminOrganizationsSafely/);
  assert.match(wiring, /refresh-admin-organizations/);
});

test('PROGRAM01 R02 binds questionnaire forms to the exact connected program key', () => {
  assert.match(source, /const connectedRef = String\(currentProgram\?\.assignment_ref/);
  assert.match(source, /const selectedRef = connectedRef \|\| storedRef/);
  assert.match(source, /aria-label="Выбранная оценка программы"/);
  assert.match(source, /<dt>Версия программы<\/dt>/);
  assert.doesNotMatch(source, /<dt>Ключ оценки<\/dt>/);
  assert.match(source, /name="assignment_ref" type="hidden"/);
});
