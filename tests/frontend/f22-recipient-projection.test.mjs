import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');

test('F22-05 shows the server projection for the recipients selected for confirm', () => {
  assert.match(organizations, /recipient_projections/);
  assert.match(organizations, /data-questionnaire-recipient-projection/);
  assert.match(wiring, /dataset\.adminProjection/);
  assert.match(wiring, /dataset\.participantProjection/);
  assert.match(wiring, /questionnaire_recipient_user/);
});
