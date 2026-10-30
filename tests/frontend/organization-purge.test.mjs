import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');

test('physical purge is shown only for inactive organizations when backend allows it', () => {
  assert.match(organizations, /physical_purge_available/);
  assert.match(organizations, /!isActive/);
  assert.match(organizations, /data-action="purge-organization"/);
  assert.match(organizations, /Удалить физически/);
});

test('physical purge requires exact code, backup reference and final confirmation', () => {
  assert.match(wiring, /confirmationCode/);
  assert.match(wiring, /confirmationCode\)\.trim\(\) !== organizationCode/);
  assert.match(wiring, /backupReference/);
  assert.match(wiring, /Backup reference обязателен/);
  assert.match(wiring, /аккаунты, identities, credentials и сессии/);
  assert.match(wiring, /Аккаунты участников других организаций сохранятся/);
  assert.match(wiring, /orphan-аккаунтами/);
  assert.match(wiring, /Действие необратимо/);
});

test('removing a member preserves their account for another organization', () => {
  assert.match(organizations, /Аккаунт сохранится; повторная регистрация не потребуется/);
  assert.match(organizations, /Убрать из участников/);
});

test('physical purge request includes all backend confirmations', () => {
  assert.match(organizations, /confirmation_code/);
  assert.match(organizations, /backup_reference/);
  assert.match(organizations, /acknowledge_irreversible: true/);
});
