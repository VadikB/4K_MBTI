import { invitationFacts, invitationMessage, invitationLinkMessage, invitationMissingText } from '../../web/js/screens/admin/invitation-presentation.js';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');
const entry = fs.readFileSync('web/js/entries/admin-organizations.js', 'utf8');
const renderSource = organizations.slice(organizations.indexOf('const renderAccountPurgeButton ='),
  organizations.indexOf('const findOrganizationMember ='))
  .replace('export const mountAdminMemberPurge', 'const mountAdminMemberPurge');
const setup = ({ actorId = 1, pending = [], canPreview = true } = {}) => {
  const context = vm.createContext({
    currentIdentityKey: () => String(actorId), pendingAdminAccountPurges: () => pending,
    state: { adminOrganizations: { purge_preview_available: canPreview } },
    findOrganizationMember: () => member,
    escapeHtml: (value) => String(value ?? '').replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;'),
    localDateTime: () => '', selectedOrganizationId: 3,
    invitationFacts, invitationMessage, invitationLinkMessage, invitationMissingText,
    invitationFor: (_org, _assessment, item) => ({ email: item.email, delivery_status: item.invitation_delivery_status || 'not_sent' }),
    savedInvitation: (item) => ({ email: item.email, delivery_status: 'not_sent' }),
    pendingInvitationOperations: () => [],
  });
  vm.runInContext(renderSource + '\nthis.members = renderMemberList; this.admins = renderOrganizationAdmins; this.mount = mountAdminMemberPurge; this.purge = renderAccountPurgeButton;', context);
  return context;
};
const member = { user_id: 20, email: 'owned@example.test', full_name: 'Synthetic person', is_admin: true };

const deletionZone = (options) => {
  const zone = { innerHTML: '', hidden: true };
  setup(options).mount({ querySelector: () => zone }, 3, 20);
  return zone;
};

test('F02 opens full deletion from the org admin card and from account actions in the history', () => {
  const adminRow = setup().members([member]).markup;
  const historyAction = setup().purge(member, { available: true });
  assert.doesNotMatch(adminRow, /data-action="purge-account"/);
  for (const markup of [historyAction, deletionZone().innerHTML]) {
    assert.match(markup, /data-action="purge-account" data-user-id="20" data-email="owned@example.test">Удалить человека/);
    assert.doesNotMatch(markup, /delete-member|restore-excluded-account|Сохранить аккаунт|Убрать из участников/);
  }
});

test('F02 permission availability is explicit and self is hidden even for superadmin', () => {
  assert.equal(deletionZone({ canPreview: false }).hidden, true);
  assert.equal(deletionZone({ actorId: 20 }).hidden, true);
  assert.equal(setup({ actorId: 20 }).purge(member, { available: true }), '');
});

test('F02 admin access shows role revocation and keeps whole-account deletion in the history', () => {
  const markup = setup().admins({ admins: [member, {
    user_id: 21, email: 'participant@example.test', is_participant: true,
  }] });
  assert.match(markup, /data-action="delete-admin"[^>]+>Снять права<\/button>/);
  assert.doesNotMatch(markup, /data-action="purge-account"/);
  assert.ok(wiring.includes('Снять права администратора?'));
  assert.ok(wiring.includes("participant === 'true' ? ' Участие сотрудника в оценке сохранится.'"));
});

test('P4K-SUP-UX-FIX-01 renders participation and permits revoking the last active admin', () => {
  const adminOnly = { ...member, is_participant: false, assessment_stages: { saved: { code: 'assigned' } } };
  const participant = { user_id: 21, email: 'participant@example.test', is_participant: true };
  const active = setup().admins({ admins: [adminOnly, participant] });
  assert.match(active, /Только административный доступ/);
  assert.match(active, /Также участник оценки/);
  assert.match(active, /data-action="add-admin"/);
  const paused = setup().admins({ is_active: false, admins: [adminOnly, participant] });
  assert.match(paused, /Доступ приостановлен/);
  assert.doesNotMatch(paused, /data-action="(?:add-admin|delete-admin)"/);
  const last = setup().admins({ admins: [adminOnly] });
  assert.match(last, /data-action="delete-admin" data-last-admin="true"/);
  assert.match(wiring, /будет 0 администраторов/);
  assert.match(setup().admins({ admins: [] }), /Администраторов пока нет/);
});

test('F02 known pending command takes recovery priority over a fresh preview or unavailable capability', () => {
  const markup = deletionZone({ pending: [{ targetUserId: 20 }], canPreview: false }).innerHTML;
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
