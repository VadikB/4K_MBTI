import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const screen = readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const styles = readFileSync('web/styles/screens/admin-organizations.css', 'utf8');

test('ADD01 requires email, name and position in the administrative member form', () => {
  assert.match(screen, /name="email"[^>]*required/);
  assert.match(screen, /name="full_name"[^>]*required/);
  assert.match(screen, /name="role_description"[^>]*required/);
  assert.match(screen, /Укажите email, ФИО и должность участника/);
});

test('ADD01 keeps the desktop member form in the measured right-hand geometry', () => {
  assert.match(styles, /grid-template-columns:\s*minmax\(0, 1fr\) 290px/);
  assert.match(styles, /\.admin-organization-member-form > h4[\s\S]*font-size:\s*20px[\s\S]*line-height:\s*28px/);
  assert.match(styles, /\.admin-organization-member-form input[\s\S]*height:\s*48px[\s\S]*font-size:\s*16px/);
});
