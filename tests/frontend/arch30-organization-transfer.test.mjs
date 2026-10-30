import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const organizations = readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = readFileSync('web/js/wiring.js', 'utf8');

test('ARCH30 renders superadmin transfer control and sends explicit source, target and role', () => {
  assert.match(organizations, /data-action="transfer-member"/);
  assert.match(organizations, /expected_source_organization_id: Number\(organizationId\)/);
  assert.match(organizations, /target_organization_id: Number\(targetOrganizationId\)/);
  assert.match(organizations, /target_role: targetRole === 'admin' \? 'admin' : 'member'/);
  assert.match(wiring, /form\.dataset\.action === 'transfer-member'/);
  assert.match(wiring, /Старые назначения и приглашения будут отозваны/);
});

test('ARCH30 explains every protected transfer conflict', () => {
  for (const code of [
    'ORGANIZATION_TRANSFER_LAST_ADMIN',
    'ORGANIZATION_TRANSFER_ACTIVE_ACQUAINTANCE',
    'ORGANIZATION_TRANSFER_SOURCE_CHANGED',
    'ORGANIZATION_TRANSFER_TARGET_INACTIVE',
  ]) assert.match(organizations, new RegExp(code));
});

test('ARCH30 keeps deactivation reversible through an explicit restore action', () => {
  assert.match(organizations, /data-action="restore-organization"/);
  assert.match(organizations, /\/restore'/);
  assert.match(wiring, /button\.dataset\.action === 'restore-organization'/);
});
