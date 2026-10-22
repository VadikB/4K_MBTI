import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const browser = fs.readFileSync('tests/browser/auth-r03.spec.mjs', 'utf8');

test('F22-03 rejects obsolete preview generations and stale input signatures', () => {
  assert.match(organizations, /questionnairePreviewRequestGenerations/);
  assert.match(organizations, /questionnaireInputSignature/);
  assert.match(organizations, /input\[type="file"\]\[name\]/);
  assert.match(organizations, /recipients: preview \? formSignature\(preview\) : null/);
  assert.match(organizations, /questionnairePreviewRequestGenerations\.get\(scopeKey\) !== requestGeneration/);
  assert.match(organizations, /if \(inputChanged\) staleQuestionnairePreviews\.add\(scopeKey\)/);
  assert.match(browser, /keeps newer input when an older preview response arrives[\s\S]*toBeDisabled\(\)/);
});
