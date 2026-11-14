import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');

test('F22-06 prefers a scoped draft and otherwise restores the confirmed revision', () => {
  assert.match(organizations, /return true;[\s\S]*restoreConfirmedRevisionForm/);
  assert.doesNotMatch(organizations, /name="source_author"/);
  assert.match(organizations, /const restoredDraft = restoreFormDraft/);
  assert.match(organizations, /if \(!restoredDraft\) restoreConfirmedRevisionForm/);
  assert.match(organizations, /purpose: answers\.C02a\?\.participant_text/);
  assert.match(organizations, /organizer: answers\.C21\?\.organizer/);
  assert.doesNotMatch(organizations, /responsible_contact: answers\.C21/);
});
