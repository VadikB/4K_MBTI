import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');

test('full deletion preview is shown to superadmin', () => {
  assert.match(organizations, /physical_purge_available/);
  assert.match(organizations, /purge_preview_available/);
  assert.match(organizations, /data-action="purge-organization"/);
  assert.match(organizations, /Удалить полностью/);
});

test('full deletion shows exact preview and keeps production execution gated', () => {
  assert.match(wiring, /previewAdminOrganizationPurge/);
  assert.match(wiring, /preview\.total_rows/);
  assert.match(wiring, /will_delete_account/);
  assert.match(wiring, /внешний журнал удаления/);
  assert.match(wiring, /confirmationCode/);
  assert.match(wiring, /confirmationCode\)\.trim\(\) !== organizationCode/);
  assert.match(wiring, /preview\.fingerprint/);
  assert.match(wiring, /Действие необратимо/);
});

test('removing a member preserves their account for another organization', () => {
  assert.match(organizations, /Аккаунт сохранится; повторная регистрация не потребуется/);
  assert.match(organizations, /Убрать из участников/);
});

test('physical purge request includes all backend confirmations', () => {
  assert.match(organizations, /confirmation_code/);
  assert.match(organizations, /preview_fingerprint/);
  assert.match(organizations, /operation_id/);
  assert.match(organizations, /acknowledge_irreversible: true/);
});

test('detached accounts remain visible when no organizations exist', () => {
  const detachedMarkupIndex = organizations.indexOf('const detachedMarkup');
  const emptyOrganizationsIndex = organizations.indexOf('if (!organizations.length)');
  assert.ok(detachedMarkupIndex >= 0 && detachedMarkupIndex < emptyOrganizationsIndex);
  assert.match(organizations, /adminOrganizationsList\.innerHTML = detachedMarkup \+ '<p class="report-empty-state">'/);
});

test('purge preview explains protected accounts', () => {
  assert.match(wiring, /preserved_reason === 'current_account'/);
  assert.match(wiring, /configured_access_will_be_revoked/);
  assert.match(wiring, /Настроенные полномочия будут отозваны/);
  assert.match(wiring, /preview\.execution_blockers/);
  assert.match(wiring, /Удаление пока заблокировано/);
});
