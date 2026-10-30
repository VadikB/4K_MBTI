import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync('web/js/screens/admin/organizations.js', 'utf8');

test('ARCH30 membership errors hide stable server code and distinguish recovery states', () => {
  assert.match(source, /ORGANIZATION_MEMBERSHIP_CONFLICT:/);
  assert.match(source, /Сессия истекла/);
  assert.match(source, /Не удалось подтвердить результат операции/);
  assert.match(source, /Не удалось связаться с сервером/);
  assert.match(source, /Произошла ошибка сервиса/);
  assert.match(source, /membershipErrorMessage\(error, 'Не удалось привязать участника\.'/);
});
