import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const interview = fs.readFileSync('web/js/screens/interview.js', 'utf8');

test('P03 confirms server presence independently of typing and requires explicit continue', () => {
  assert.match(interview, /contract\.heartbeat_interval_seconds/);
  assert.match(interview, /setTimeout\(tick, intervalSeconds \* 1000\)/);
  assert.doesNotMatch(interview, /heartbeatProductPresence\(\); \}, 10000/);
  assert.match(interview, /\/presence/);
  assert.match(interview, /return-state/);
  assert.match(interview, /saved\.return_policy_enabled && saved\.current_situation && returnPresenceCycleId !== saved\.cycle_id/);
  assert.match(interview, /presenceContract = await heartbeatProductPresence\(\)/);
  assert.match(interview, /saved\.return_policy_enabled && snapshot\.current_situation/);
  assert.match(interview, /return-continue/);
  assert.match(interview, /if \(await loadReturnState\(\{ generation \}\)\) return null/);
  assert.match(interview, /M7_RETURN_CURRENT_POSITION_NOT_FOUND/);
  assert.match(interview, /await heartbeatProductPresence\(\);\s*if \(!current\(\)\) return;\s*await loadProductRuntime\(\)/);
  assert.match(interview, /const pending = pendingReturnContinue\(value\)/);
  assert.match(interview, /idempotency_key: pending\.generationKey/);
  assert.match(interview, /idempotency_key: pending\.key/);
  assert.match(interview, /clearConfirmedReturnContinue\(saved\)/);
  assert.match(interview, /state\.assessmentTotalCases = totalPositions/);
  assert.match(interview, /if \(!\(await loadReturnState\(\)\)\)/);
  assert.match(interview, /Продолжить/);
});

test('P03 blocks stopped AS input and uses admitted equivalent candidate for replacement', () => {
  assert.match(interview, /interviewTextarea\.disabled = true/);
  assert.match(interview, /equivalent-candidate/);
  assert.match(interview, /provider_config_ref/);
  assert.match(interview, /Частичный диалог не переносится/);
});

test('P3-B keeps unknown timing distinct from zero or unlimited time', () => {
  assert.match(interview, /serverRemainingSeconds/);
  assert.match(interview, /Остаток времени выполнения уточняется/);
  assert.match(interview, /Время уточняется/);
  assert.doesNotMatch(interview, /value\.remaining_seconds \|\| 0/);
  assert.doesNotMatch(interview, /prefix \+ 'Без лимита'/);
});
