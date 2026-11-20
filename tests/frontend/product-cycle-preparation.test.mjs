import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const helper = fs.readFileSync('web/js/product-cycle-preparation.js', 'utf8');
const onboarding = fs.readFileSync('web/js/screens/onboarding.js', 'utf8');
const interview = fs.readFileSync('web/js/screens/interview.js', 'utf8');
const cycleStart = fs.readFileSync('web/js/product-cycle-start.js', 'utf8');

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

test('first start reconciles a lost POST response through read-only runtime', () => {
  assert.match(interview, /startPreparedProductCycle\(state\.productCycleId\)/);
  assert.match(cycleStart, /\/assessment\/cycles\/start/);
  assert.match(cycleStart, /\/assessment\/cycles\/.*\/runtime/);
  assert.match(cycleStart, /current_situation\?\.status !== 'admitted'/);
  assert.match(cycleStart, /participant_payload/);
  assert.match(cycleStart, /AssessmentStartUnknown/);
  assert.doesNotMatch(cycleStart, /prepareProductCycle|cycles\/prepare/);
});

test('functional next uses a durable preparation and a separate explicit presentation', () => {
  assert.ok(interview.includes("post(path + '/next',"));
  assert.ok(interview.includes("after_assessment_situation_id: afterAs"));
  assert.ok(interview.includes("await read(pending.operationId)"));
  assert.ok(interview.includes("post(path + '/present-next', snapshot.next_presentation)"));
  assert.ok(interview.includes("['NO_ADMISSIBLE_CASE', 'OUT_OF_TIME']"));
});
