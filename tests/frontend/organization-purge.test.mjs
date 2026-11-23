import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');
const history = fs.readFileSync('web/js/screens/admin/organization-history.js', 'utf8');

test('full deletion preview is shown to superadmin', () => {
  assert.match(organizations, /physical_purge_available/);
  assert.match(organizations, /purge_preview_available/);
  assert.match(organizations, /mountOrganizationHistory/);
  assert.match(history, /Удалить полностью/);
});

test('full deletion shows exact preview and keeps production execution gated', () => {
  assert.match(history, /\/purge-preview/);
  assert.match(history, /preview\.total_rows/);
  assert.match(history, /preview\.execution_available === true/);
  assert.match(history, /code !== organization\.code/);
  assert.match(history, /preview\.fingerprint/);
  assert.match(history, /Действие необратимо/);
});

test('deleting a person uses the same full account operation from the member card and superadmin list', () => {
  assert.match(organizations, /Удалить человека/);
  assert.match(organizations, /const removeButton = isSuperadmin \? renderAccountPurgeButton/);
  assert.match(organizations, /mountAdminMemberPurge[\s\S]+renderAccountPurgeButton\(item, \{ available: state\.adminOrganizations\?\.purge_preview_available === true/);
  assert.match(wiring, /closest\('dialog \[data-card-delete\] button\[data-action\]'\)/);
  assert.doesNotMatch(organizations, /Аккаунт сохранится; повторная регистрация не потребуется|Убрать из участников/);
});

test('physical purge request includes all backend confirmations', () => {
  assert.match(history, /confirmation_code/);
  assert.match(history, /preview_fingerprint/);
  assert.match(history, /operation_id/);
  assert.match(history, /acknowledge_irreversible: true/);
});

test('account operation recovery remains available without a remaining organization', () => {
  assert.match(organizations, /const pendingPurges = pendingAdminAccountPurges\(\)/);
  assert.match(organizations, /adminOrganizationsList\.innerHTML = purgeRecoveryMarkup \+ staleMarkup \+ '<p class="report-empty-state">'/);
  assert.doesNotMatch(organizations, /excluded_accounts|detached_accounts|restore-excluded-account/);
});

test('purge preview explains protected accounts', () => {
  assert.match(history, /preserved_reason === 'current_account'/);
  assert.match(history, /preserved_reason === 'configured_account'/);
  assert.match(history, /configured_access_will_be_revoked/);
  assert.match(history, /Настроенные полномочия будут отозваны/);
  assert.match(history, /preview\.execution_blockers/);
  assert.match(history, /Удаление пока заблокировано/);
});
