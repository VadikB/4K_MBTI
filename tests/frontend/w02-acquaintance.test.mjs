import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const onboarding = fs.readFileSync('web/js/screens/onboarding.js', 'utf8');
const interview = fs.readFileSync('web/js/screens/interview.js', 'utf8');
const router = fs.readFileSync('web/js/router.js', 'utf8');
const productPreparation = fs.readFileSync('web/js/product-cycle-preparation.js', 'utf8');

test('W02 uses server briefing, saves each answer and confirms all three before 4K', () => {
  assert.match(onboarding, /readiness\.briefing/);
  assert.match(onboarding, /answer_\$\{index \+ 1\}/);
  assert.match(onboarding, /confirm: false/);
  assert.match(onboarding, /confirm: true/);
  assert.match(onboarding, /Что показывает оценка 4К/);
  assert.match(onboarding, /prepareProductCycle/);
  assert.match(productPreparation, /assessment\/cycles\/prepare/);
});

test('W02 keeps preparation separate from explicit assessment start', () => {
  assert.match(interview, /if \(!state\.productCycleId\)/);
  assert.match(interview, /assessment\/cycles\/start/);
  assert.match(router, /Проверить готовность/);
  assert.doesNotMatch(router, /invitation_intro/);
  const entry = interview.slice(interview.indexOf('export const handleAssessmentEntryClick'));
  assert.match(entry, /loadUserJourneyState/);
  assert.match(entry, /journey.next_action === 'show_onboarding'/);
  assert.match(entry, /openOnboardingScreen/);
});

test('W02 displays server-resolved assignment timing and restores the prepared snapshot', () => {
  assert.match(onboarding, /assigned_timing\?\.status === 'resolved'/);
  assert.match(onboarding, /Время на выполнение/);
  assert.match(onboarding, /Ситуации/);
  assert.match(onboarding, /Завершить оценку нужно в течение/);
  assert.match(onboarding, /Приступить к оценке/);
  assert.match(onboarding, /preparedPlanSnapshot\?\.plan/);
  assert.doesNotMatch(onboarding, /Назначенный общий бюджет/);
  assert.doesNotMatch(onboarding, /Ориентировочная общая длительность/);
  assert.doesNotMatch(onboarding, /(?:default|fallback).*60/i);
});

test('UX-AUD29-05 explains return from the saved policy instead of snapshot truthiness', () => {
  assert.match(onboarding, /resume_mode === 'same_assessment_situation'/);
  assert.match(onboarding, /продолжите ту же незавершённую ситуацию/);
  assert.match(onboarding, /resume_mode === 'replace_assessment_situation'/);
  assert.doesNotMatch(onboarding, /return_policy_snapshot \?[^:]+может обновиться/);
});

test('W02 closes one situation and requires an explicit start for the next one', () => {
  assert.match(interview, /finish-situation/);
  assert.match(interview, /Приступить к следующей ситуации/);
  assert.match(interview, /snapshot\.between_situations/);
});

test('Cycle progress is based on route positions rather than generated situations', () => {
  assert.match(interview, /snapshot\.route\?\.positions/);
  assert.match(interview, /currentPosition\?\.position_no/);
  assert.match(interview, /total_positions/);
  assert.doesNotMatch(interview, /assessmentCaseNumber = Math\.max\(1, snapshot\.situations\?\.length/);
});
