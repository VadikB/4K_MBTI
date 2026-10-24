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
  assert.match(helper, /return operation\.result/);
  assert.match(helper, /operation\.error\?\.message/);
  assert.doesNotMatch(helper, /result_json|error_message/);
  assert.match(onboarding, /prepareProductCycle\(/);
  assert.match(interview, /prepareProductCycle\(/);
  assert.doesNotMatch(onboarding, /fetch\('\/users\/assessment\/cycles\/prepare'/);
  assert.doesNotMatch(interview, /fetch\('\/users\/assessment\/cycles\/prepare'/);
});

test('functional next situation waits for durable generation and admission', () => {
  assert.match(interview, /fetch\('\/users\/assessment\/m7\/cycles\/' \+ encodeURIComponent\(state\.productCycleId\) \+ '\/next'/);
  assert.match(interview, /accepted\.operation_id \? await waitForProductCyclePreparation\(accepted\) : accepted/);
  assert.match(interview, /if \(accepted\.operation_id\) await waitForProductCyclePreparation\(accepted\)/);
  assert.match(interview, /next\.decision\?\.status === 'WAITING_CURRENT_AS'/);
  assert.match(interview, /next\.decision\?\.status === 'COLLECTION_CLOSED'/);
  assert.match(interview, /\['NO_ADMISSIBLE_CASE', 'OUT_OF_TIME'\]/);
});
