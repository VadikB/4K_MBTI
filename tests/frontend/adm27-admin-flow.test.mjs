import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const organizations = readFileSync(new URL('../../web/js/screens/admin/organizations.js', import.meta.url), 'utf8');
const wiring = readFileSync(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');

test('the organization administrator can invite eligible participants in the people list', () => {
  assert.match(organizations, /const invitationCandidate = activeOrganization && !registered && awaitingParticipant/);
  assert.match(organizations, /const send = canSend \?[^\n]+send-member-invitation/);
});

test('member form resets only after confirmed success', () => {
  assert.match(wiring, /const added = await module\.addAdminOrganizationMember/);
  assert.match(wiring, /if \(added\) form\.reset\(\)/);
});

test('manual questionnaire draft fields are not blocked by publish required attributes', () => {
  const start = organizations.indexOf('data-action="preview-early-data"');
  const end = organizations.indexOf('</form>', start);
  assert.ok(start > 0 && end > start);
  assert.doesNotMatch(organizations.slice(start, end), /name="(?:organization_name|purpose|organizer)"[^>]* required/);
});

test('ADM 1A uses the accepted navigation, groups and provenance wording', () => {
  assert.match(organizations, /people:\s*\{\s*title: 'Участники оценки'/);
  assert.match(organizations, /managementSections\.map\(viewButton\)/);
  assert.match(organizations, /<legend>Об организации<\/legend>/);
  assert.match(organizations, /<legend>Сведения для знакомства<\/legend>/);
  assert.match(organizations, /<legend>Настройки контекста для ситуаций<\/legend>/);
  assert.match(organizations, /Близость ситуаций к реальной работе/);
  assert.match(organizations, /Название организации в ситуациях/);
  assert.match(organizations, /payload\?\.channel === 'csv'[\s\S]*Анкета загружена[\s\S]*Черновик сохранён/);
  assert.doesNotMatch(organizations, /Первая публикация|Анкета распознана|Обязательные поля распознаны/);
});

test('selected members can receive an explicit assessment assignment', () => {
  assert.match(organizations, /assessment-assignments/);
  assert.match(wiring, /form\.dataset\.action === 'assign-member-assessment'/);
  assert.match(organizations, /role_profile_version_id/);
  assert.match(wiring, /formData\.get\('role_profile_version_id'\)/);
});
