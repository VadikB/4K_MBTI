import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const helper = fs.readFileSync('web/js/product-cycle-preparation.js', 'utf8');
const onboarding = fs.readFileSync('web/js/screens/onboarding.js', 'utf8');
const interview = fs.readFileSync('web/js/screens/interview.js', 'utf8');

test('product Cycle preparation polls the operation and exposes only completed result', () => {
  assert.match(helper, /\/assessment\/cycles\/preparation\//);
  assert.match(helper, /operation\.status === 'completed'/);
  assert.match(helper, /operation\.status === 'failed'/);
  assert.match(onboarding, /prepareProductCycle\(/);
  assert.match(interview, /prepareProductCycle\(/);
  assert.doesNotMatch(onboarding, /fetch\('\/users\/assessment\/cycles\/prepare'/);
  assert.doesNotMatch(interview, /fetch\('\/users\/assessment\/cycles\/prepare'/);
});
