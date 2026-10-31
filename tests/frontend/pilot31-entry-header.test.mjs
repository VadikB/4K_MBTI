import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const html = fs.readFileSync(new URL('../../web/index.html', import.meta.url), 'utf8');
const components = fs.readFileSync(new URL('../../web/styles/components.css', import.meta.url), 'utf8');
const onboarding = fs.readFileSync(new URL('../../web/styles/screens/onboarding.css', import.meta.url), 'utf8');

test('auth shell and onboarding expose release badges outside auth cards', () => {
  assert.match(html, /<header class="entry-header" data-entry-header>/);
  assert.doesNotMatch(html, /auth-external-brand/);
  assert.equal((html.match(/data-app-release-badge/g) || []).length, 3);
  assert.match(html, /onboarding-brand-lockup[\s\S]*data-app-release-badge/);
});

test('entry and onboarding headers keep approved desktop and mobile geometry', () => {
  assert.match(components, /\.entry-header\s*\{[\s\S]*flex:\s*0 0 80px/);
  assert.match(components, /padding-inline:\s*64px/);
  assert.match(components, /\.entry-release-badge\s*\{[\s\S]*min-height:\s*24px/);
  assert.match(components, /@media \(max-width: 479px\)[\s\S]*flex-basis:\s*64px/);
  assert.match(onboarding, /\.onboarding-section-label\s*\{[\s\S]*left:\s*50%[\s\S]*translateX\(-50%\)/);
  assert.match(onboarding, /@media \(max-width: 600px\)[\s\S]*flex-direction:\s*column/);
});

test('new header does not hardcode retired release examples', () => {
  assert.doesNotMatch(html, /2\.0\.42|2\.1\.28/);
});
