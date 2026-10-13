import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web/index.html', import.meta.url), 'utf8');
const wiring = await readFile(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');
const session = await readFile(new URL('../../web/js/session.js', import.meta.url), 'utf8');
const dashboardEntry = await readFile(new URL('../../web/js/entries/dashboard.js', import.meta.url), 'utf8');

test('auth forms expose password-manager fields and an explicit way to change email', () => {
  assert.match(html, /autocomplete="username email"/);
  assert.match(html, /autocomplete="new-password"/);
  assert.match(html, /id="auth-change-credential-email-button"/);
  assert.match(wiring, /authChangeCredentialEmailButton\.addEventListener\('click'/);
  assert.match(wiring, /showPasswordCreationStep\(\)/);
});

test('registration and repeat login route through the existing journey without auth-complete', () => {
  assert.match(wiring, /loadUserJourneyState/);
  assert.match(wiring, /next_action === 'show_onboarding'/);
  assert.match(wiring, /next_action === 'resume_assessment'/);
  assert.doesNotMatch(session, /state\.currentScreen = 'auth-complete'/);
  assert.match(dashboardEntry, /openDashboard/);
});

test('mutating auth actions guard repeated submissions and expose busy state', () => {
  assert.match(wiring, /if \(authRequestInFlight\) return/);
  assert.match(wiring, /if \(authCredentialInFlight\) return/);
  assert.match(wiring, /if \(authResetRequestInFlight \|\| authCredentialInFlight\) return/);
  assert.match(wiring, /forgotPasswordCredentialButton\]/);
  assert.match(wiring, /setAttribute\('aria-busy', 'true'\)/);
});

test('new passwords use two in-memory steps and the accepted ASCII policy', () => {
  assert.match(wiring, /let newPasswordDraft = ''/);
  assert.match(wiring, /showPasswordConfirmationStep/);
  assert.match(wiring, /\[!-~\]\{10,/);
  assert.match(wiring, /while \(chars\.length < 10\)/);
  assert.doesNotMatch(wiring, /sessionStorage.*newPasswordDraft|localStorage.*newPasswordDraft/);
  assert.match(html, /Требования к паролю/);
  assert.match(html, /Без пробелов и кириллицы/);
});
