import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const onboarding = fs.readFileSync('web/js/screens/onboarding.js', 'utf8');
const interview = fs.readFileSync('web/js/screens/interview.js', 'utf8');
const router = fs.readFileSync('web/js/router.js', 'utf8');

test('W02 uses server briefing, saves each answer and confirms all three before 4K', () => {
  assert.match(onboarding, /readiness\.briefing/);
  assert.match(onboarding, /answer_\$\{index \+ 1\}/);
  assert.match(onboarding, /confirm: false/);
  assert.match(onboarding, /confirm: true/);
  assert.match(onboarding, /Что показывает оценка 4К/);
  assert.match(onboarding, /assessment\/cycles\/prepare/);
});

test('W02 keeps preparation separate from explicit assessment start', () => {
  assert.match(interview, /if \(!state\.productCycleId\)/);
  assert.match(interview, /assessment\/cycles\/start/);
  assert.match(router, /Проверить готовность/);
  assert.doesNotMatch(router, /invitation_intro/);
});
