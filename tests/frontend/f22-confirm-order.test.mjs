import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');

test('F22-04 keeps newer server revisions and post-submit drafts', () => {
  assert.match(organizations, /questionnaireConfirmRequestGenerations/);
  assert.match(organizations, /fetch\('\/users\/admin\/organizations\/' \+ organizationId \+ '\/questionnaire'/);
  assert.match(organizations, /isQuestionnaireRevisionNewer\(currentRevision, confirmed\)/);
  assert.match(organizations, /currentCard\?\.querySelector\('form\[data-action=/);
  assert.match(organizations, /formSignature\(form\) === signature/);
  assert.match(organizations, /captureFormDraft\(organizationId, form\)/);
  assert.match(organizations, /if \(!changedActions\.has\(action\)\)/);
  assert.match(organizations, /Показана более новая серверная редакция/);
});
