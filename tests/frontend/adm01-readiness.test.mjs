import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const organizations = await readFile('web/js/screens/admin/organizations.js', 'utf8');
const wiring = await readFile('web/js/wiring.js', 'utf8');
const styles = await readFile('web/styles/screens/admin-organizations.css', 'utf8');

test('ADM01 keeps participant invitations bound to the selected assessment', () => {
  assert.match(organizations, /assignment_ref: assessment/);
  assert.match(organizations, /Данные организации/);
  assert.match(organizations, /Можно приглашать участников/);
  assert.match(wiring, /getSelectedAdminOrganizationAssessment/);
  assert.doesNotMatch(wiring, /sendAdminOrganizationMemberInvitation\([\s\S]{0,160}querySelector\('input\[name="assignment_ref"\]'/);
});

test('ADM01 admin surface uses the accepted readiness and control colors', () => {
  assert.match(styles, /background: #b3ebef/);
  assert.match(styles, /background: #222c30/);
  assert.match(styles, /border-color: var\(--accent\)/);
  assert.doesNotMatch(organizations, /Администратор организации|Моя организация/);
});
