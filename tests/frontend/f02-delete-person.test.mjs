import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');
const entry = fs.readFileSync('web/js/entries/admin-organizations.js', 'utf8');
const renderSource = organizations.slice(organizations.indexOf('const renderAccountPurgeButton ='),
  organizations.indexOf('export const renderAdminOrganizations ='));
const setup = ({ actorId = 1, pending = [] } = {}) => {
  const context = vm.createContext({
    currentIdentityKey: () => String(actorId), pendingAdminAccountPurges: () => pending,
    escapeHtml: (value) => String(value ?? '').replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;'),
    localDateTime: () => '',
  });
  vm.runInContext(renderSource + '\nthis.members = renderMemberList; this.tags = renderTagList;', context);
  return context;
};
const member = { user_id: 20, email: 'owned@example.test', full_name: 'Synthetic person', is_admin: true };

test('F02 org admin and superadmin current participant controls directly delete the whole person', () => {
  for (const isSuperadmin of [false, true]) {
    const markup = setup().members([member], { isSuperadmin, canDeletePerson: true });
    assert.match(markup, /data-action="purge-account" data-user-id="20" data-email="owned@example.test">Удалить человека/);
    assert.doesNotMatch(markup, /delete-member|restore-excluded-account|Сохранить аккаунт|Убрать из участников/);
  }
});

test('F02 permission availability is explicit and self is hidden even for superadmin', () => {
  assert.doesNotMatch(setup().members([member]), /data-action="purge-account"/);
  assert.doesNotMatch(setup({ actorId: 20 }).members([member], {
    isSuperadmin: true, canDeletePerson: true,
  }), /data-action="purge-account"/);
});

test('F02 current administrator has separate named revoke-rights and whole-account controls', () => {
  const markup = setup().tags([member], '', 'admin', 'delete-admin', { canDeletePerson: true });
  assert.match(markup, /data-action="delete-admin"[^>]+>Снять права<\/button>/);
  assert.match(markup, /data-action="purge-account"[^>]+>Удалить человека<\/button>/);
  assert.ok(wiring.includes('Снять административный доступ у '));
  assert.ok(wiring.includes('Участие в оценке и аккаунт сохранятся.'));
});

test('F02 known pending command takes recovery priority over a fresh preview or unavailable capability', () => {
  const markup = setup({ pending: [{ targetUserId: 20 }] }).members([member], { canDeletePerson: false });
  assert.match(markup, /data-action="recover-purge-account"[^>]+>Проверить удаление<\/button>/);
  assert.doesNotMatch(markup, /data-action="purge-account"/);
});

test('F02 obsolete exclude, restore and transfer user flows have no renderer, handler or export', () => {
  for (const source of [organizations, wiring, entry]) {
    assert.doesNotMatch(source, /excluded_accounts|detached_accounts|restoreExcludedAccountForm|restore-excluded-account|deleteAdminOrganizationMember|data-action="delete-member"|dataset\.action === 'delete-member'|transferAdminOrganizationMember|transfer-member/);
  }
  assert.match(wiring, /Все функции участника и администратора, доступ, оценки и отчёты этого человека будут удалены/);
  assert.doesNotMatch(wiring, /Autotest-пользователей нельзя отвязывать|Аккаунт, административный доступ, назначения и история сохранятся/);
});
