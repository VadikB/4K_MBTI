import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const organizations = readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = readFileSync('web/js/wiring.js', 'utf8');
const entry = readFileSync('web/js/entries/admin-organizations.js', 'utf8');
const history = readFileSync('web/js/screens/admin/organization-history.js', 'utf8');

test('ARCH30 removes organization transfer from the product UI', () => {
  assert.doesNotMatch(organizations, /data-action="transfer-member"/);
  assert.doesNotMatch(organizations, /transferAdminOrganizationMember/);
  assert.doesNotMatch(wiring, /form\.dataset\.action === 'transfer-member'/);
  assert.doesNotMatch(entry, /transferAdminOrganizationMember/);
});

test('ARCH30 removes obsolete transfer conflict copy', () => {
  assert.doesNotMatch(organizations, /ORGANIZATION_TRANSFER_LAST_ADMIN/);
  assert.doesNotMatch(organizations, /ORGANIZATION_TRANSFER_ACTIVE_ACQUAINTANCE/);
});

test('ARCH30 keeps deactivation reversible through an explicit restore action', () => {
  assert.match(history, /Восстановить организацию/);
  assert.match(history, /\/restore'/);
  assert.match(history, /dialog\.returnValue !== 'confirm'/);
});
