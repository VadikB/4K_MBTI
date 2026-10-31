import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const organizations = readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const routes = readFileSync('Api/routes.py', 'utf8');
const styles = readFileSync('web/styles/screens/admin-organizations.css', 'utf8');

test('ARCH30 shows one current participant stage and keeps raw signals in details', () => {
  for (const label of [
    'Приглашение не отправлено',
    'Письмо отправлено — ожидаем начала знакомства',
  ]) assert.match(organizations, new RegExp(label));
  for (const label of [
    'Проходит знакомство',
    'Идёт подготовка оценки',
    'Подготовка завершилась с ошибкой',
    'Оценка подготовлена',
    'Можно начинать оценку',
    'Проходит оценку',
    'Результат обрабатывается',
    'Отчёт готов',
  ]) assert.match(routes, new RegExp(label));
  assert.match(organizations, /assessment_stages\?\.\[selectedAssessmentRef\]/);
  assert.match(routes, /job\.personalized_profile_id=profile\.id/);
  assert.match(routes, /runtime\.organization_id=assignment\.organization_id/);
  assert.match(routes, /acquaintance\.assignment_ref=assignment\.assignment_ref/);
  assert.match(organizations, /<details class="admin-organization-member-statuses">/);
  assert.match(organizations, /Подробности статуса/);
  assert.match(styles, /\.admin-organization-current-stage/);
  assert.match(styles, /overflow-wrap: anywhere/);
});
