import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const organizations = readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const routes = readFileSync('Api/routes.py', 'utf8');
const styles = readFileSync('web/styles/screens/admin-organizations.css', 'utf8');

test('ADM-STATUS-01 shows one current participant stage and keeps secondary signals in the card', () => {
  for (const label of ['Оценка назначена', 'Оценка не назначена', 'Подготовка заблокирована']) {
    assert.match(organizations, new RegExp(label));
  }
  for (const label of [
    'Проходит знакомство',
    'Идёт подготовка оценки',
    'Подготовка завершилась с ошибкой',
    'Готов к прохождению оценки',
    'Проходит оценку',
    'Готовится отчёт',
    'Отчёт готов',
  ]) assert.match(routes, new RegExp(label));
  assert.match(organizations, /assessment_stages\?\.\[selectedAssessmentRef\]/);
  assert.match(routes, /job\.personalized_profile_id=profile\.id/);
  assert.match(routes, /runtime\.organization_id=assignment\.organization_id/);
  assert.match(routes, /acquaintance\.assignment_ref=assignment\.assignment_ref/);
  assert.match(organizations, /data-action="open-member-card"/);
  assert.match(organizations, /class="admin-organization-member-stage"/);
  assert.match(organizations, /aria-label="Другие действия"/);
  assert.doesNotMatch(organizations, /<details class="admin-organization-member-statuses">/);
  assert.match(styles, /\.admin-organization-current-stage/);
  assert.match(styles, /overflow-wrap: anywhere/);
});

test('ADM-STATUS-01 keeps destructive participant operations separate and explicit', () => {
  assert.match(organizations, /Отозвать приглашение/);
  assert.match(organizations, /Отменить назначение оценки/);
  assert.match(organizations, /data-assignment-id/);
  assert.match(organizations, /cancelAdminOrganizationAssessment/);
  assert.match(routes, /assessment-assignments\/\{assignment_id\}\/cancel/);
});

test('ADM-STATUS-01 scopes preserved participant selection by organization and assessment', () => {
  assert.match(organizations, /':participant-selection:' \+ assessmentRef/);
  assert.doesNotMatch(organizations, /participant-selection:organization/);
});
