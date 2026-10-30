import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const organizations = readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const styles = readFileSync('web/styles/screens/admin-organizations.css', 'utf8');

test('ARCH30 shows one current participant stage and keeps raw signals in details', () => {
  for (const label of [
    'Приглашение не отправлено',
    'Письмо отправлено — ожидаем начала знакомства',
    'Проходит знакомство',
    'Идёт подготовка оценки',
    'Подготовка завершилась с ошибкой',
    'Оценка подготовлена',
  ]) assert.match(organizations, new RegExp(label));
  assert.match(organizations, /<details class="admin-organization-member-statuses">/);
  assert.match(organizations, /Подробности статуса/);
  assert.match(styles, /\.admin-organization-current-stage/);
  assert.match(styles, /overflow-wrap: anywhere/);
});
