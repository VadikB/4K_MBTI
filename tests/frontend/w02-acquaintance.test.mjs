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

test('W02 closes one situation and requires an explicit start for the next one', () => {
  assert.match(interview, /finish-situation/);
  assert.match(interview, /Приступить к следующему кейсу/);
  assert.match(interview, /snapshot\.between_situations/);
});

test('Cycle progress is based on route positions rather than generated situations', () => {
  assert.match(interview, /snapshot\.route\?\.positions/);
  assert.match(interview, /currentPosition\?\.position_no/);
  assert.match(interview, /total_positions/);
  assert.doesNotMatch(interview, /assessmentCaseNumber = Math\.max\(1, snapshot\.situations\?\.length/);
});
