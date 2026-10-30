import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const organizations = readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const wiring = readFileSync('web/js/wiring.js', 'utf8');

test('ARCH30 removes the duplicate legacy organization profile field from both admin forms', () => {
  assert.doesNotMatch(organizations, /Профиль организации/);
  assert.doesNotMatch(organizations, /textarea name="profile"/);
  assert.doesNotMatch(wiring, /profile: String\(formData\.get\('profile'\)/);
  assert.match(organizations, /Описание деятельности/);
  assert.match(organizations, /name="activity_description"/);
});

test('ARCH30 exposes a legacy profile as an explicit C01 migration draft without automatic overwrite', () => {
  assert.match(organizations, /Сохранённое описание из прежней карточки/);
  assert.match(organizations, /data-action="use-legacy-profile"/);
  assert.match(organizations, /currentActivityDescription/);
  assert.match(organizations, /не перезаписывает подтверждённые сведения/);
  assert.doesNotMatch(organizations, /name="profile"/);
});
