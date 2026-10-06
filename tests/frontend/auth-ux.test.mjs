import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web/index.html', import.meta.url), 'utf8');
const wiring = await readFile(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');
const session = await readFile(new URL('../../web/js/session.js', import.meta.url), 'utf8');

test('auth forms expose password-manager fields and an explicit way to change email', () => {
  assert.match(html, /autocomplete="username email"/);
  assert.match(html, /autocomplete="new-password"/);
  assert.match(html, /id="auth-change-credential-email-button"/);
  assert.match(wiring, /authChangeCredentialEmailButton\.addEventListener\('click', showEmailEntry\)/);
});

test('ordinary login and session restore route to the neutral auth-complete destination', () => {
  assert.match(html, /id="auth-complete-panel"/);
  assert.match(html, /Следующий этап готовится/);
  assert.doesNotMatch(html.match(/<section class="panel auth-complete-panel[\s\S]*?<\/section>/)?.[0] || '', /assessment|оценк/i);
  assert.match(wiring, /openAuthComplete\(\)/);
  assert.match(session, /state\.currentScreen = 'auth-complete'/);
});

test('mutating auth actions guard repeated submissions and expose busy state', () => {
  assert.match(wiring, /if \(authRequestInFlight\) return/);
  assert.match(wiring, /if \(authCredentialInFlight\) return/);
  assert.match(wiring, /if \(authResetRequestInFlight\) return/);
  assert.match(wiring, /setAttribute\('aria-busy', 'true'\)/);
});
