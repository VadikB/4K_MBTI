import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const logout = readFileSync('web/js/logout-ui.js', 'utf8');
const html = readFileSync('web/index.html', 'utf8');

test('ARCH30 logout reset covers every current logout and exit button by contract', () => {
  assert.match(logout, /button\[id\$="-logout-button"\]/);
  assert.match(logout, /button\[id\$="-exit-button"\]/);
  const ids = [...html.matchAll(/id="([^"]+(?:logout|exit)-button)"/g)].map((match) => match[1]);
  assert.ok(ids.includes('auth-complete-logout-button'));
  assert.ok(ids.includes('admin-organizations-logout-button'));
  assert.ok(ids.includes('admin-assessment-empty-logout-button'));
});
