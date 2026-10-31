import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const organizations = readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const routes = readFileSync('Api/routes.py', 'utf8');
const styles = readFileSync('web/styles/screens/admin-organizations.css', 'utf8');

test('ADM-STATUS shows one current participant stage and moves secondary operations into a menu', () => {
  for (const label of [
    'Приглашение не отправлено',
    'Письмо отправлено — ожидаем начала знакомства',
  ]) assert.match(organizations, new RegExp(label));
  for (const label of [
    'Проходит знакомство',
    'Идёт подготовка оценки',
    'Подготовка завершилась с ошибкой',
    'Готов к прохождению оценки',
    'Проходит оценку',
    'Готовится отчёт',
    'Отчёт готов',
    'Назначение отменено',
  ]) assert.match(routes, new RegExp(label));
  assert.match(organizations, /assessment_stages\?\.\[selectedAssessmentRef\]/);
  assert.match(routes, /job\.personalized_profile_id=profile\.id/);
  assert.match(routes, /runtime\.organization_id=assignment\.organization_id/);
  assert.match(routes, /acquaintance\.assignment_ref=assignment\.assignment_ref/);
  assert.match(organizations, /Готов к прохождению оценки/);
  assert.match(organizations, /Ожидаем начала/);
  assert.match(organizations, /<details class="admin-organization-member-menu">/);
  assert.doesNotMatch(organizations, /Отозвать ссылку/);
  assert.match(organizations, /Отозвать приглашение/);
  assert.match(organizations, /data-action="cancel-member-assignment"/);
  assert.match(organizations, /Отменить назначение оценки/);
  assert.match(routes, /runtime\.assignment_id=assignment\.id/);
  assert.match(styles, /\.admin-organization-current-stage/);
  assert.match(styles, /\.admin-organization-member-menu/);
  assert.match(styles, /overflow-wrap: anywhere/);
});
