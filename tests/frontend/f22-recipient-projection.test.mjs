import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');

test('REMAIN-02 shows the server access explanation without recipient controls', () => {
  assert.match(organizations, /questionnairePreview\?\.participant_preview/);
  assert.match(organizations, /result_recipients: 'Доступ к готовым отчётам'/);
  assert.doesNotMatch(organizations, /recipient_projections/);
  assert.doesNotMatch(organizations, /questionnaire_recipient_user/);
  assert.doesNotMatch(wiring, /questionnaire_recipient_user/);
});
