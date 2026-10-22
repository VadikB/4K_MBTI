import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { createAdminOrganizationDraftKey } from '../../web/js/screens/admin/organization-draft-key.js';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const draftKey = fs.readFileSync('web/js/screens/admin/organization-draft-key.js', 'utf8');

test('F22-02 scopes questionnaire recipient drafts by assignment and revision', () => {
  const key = (assessmentRef, revisionId) => createAdminOrganizationDraftKey({
    identityKey: '18', organizationId: 3, action: 'questionnaire-preview', assessmentRef, revisionId,
  });
  assert.notEqual(key('Поток A', 101), key('Поток B', 102));
  assert.notEqual(key('Поток A', 101), key('Поток A', 102));
  assert.notEqual(key('Поток A', 101), createAdminOrganizationDraftKey({
    identityKey: '19', organizationId: 3, action: 'questionnaire-preview', assessmentRef: 'Поток A', revisionId: 101,
  }));
  assert.equal(key('Поток A', 101), '18:3:questionnaire-preview:Поток A:101');

  assert.match(organizations, /dataset\?\.draftAction \|\| form\?\.dataset\?\.action/);
  assert.match(draftKey, /'questionnaire-preview'/);
  assert.match(organizations, /form\?\.dataset\?\.assessmentRef/);
  assert.match(organizations, /questionnaireRevisionId/);
  assert.match(organizations, /data-draft-action="questionnaire-preview"/);
  assert.match(organizations, /data-questionnaire-revision-id=/);
});
