import test from 'node:test';
import assert from 'node:assert/strict';
import { assessmentPositionText, assessmentMetadata, formatAssessmentDate } from '../../web/js/dashboard-presentation.js';
const active = { status: 'active', journey_state: 'active', planned_total: 8, current_position_no: 3 };
test('POSTW02 shows saved current position even when completed is unknown', () => {
  for (const completed_cases of [undefined, null, 0, 2, '0']) {
    assert.equal(assessmentPositionText({ ...active, completed_cases, total_cases: 3 }), '3 ситуация из 8');
  }
});
test('POSTW02 never infers a current position or total from materialized/completed counts', () => {
  for (const current_position_no of [undefined, null, '3', 0, 9]) {
    assert.equal(assessmentPositionText({ ...active, current_position_no, completed_cases: 2 }), '8 ситуаций в плане');
  }
  assert.equal(assessmentPositionText({ ...active, planned_total: null, total_cases: 9 }), '');
  assert.equal(assessmentPositionText({ ...active, status: 'prepared' }), '8 ситуаций в плане');
});
test('POSTW02 between screen stays on last presented closed position', () => {
  assert.equal(assessmentPositionText({ ...active, journey_state: 'between_situations', last_completed_position_no: 3 }), 'Ситуация 3 завершена');
  assert.equal(assessmentPositionText({ ...active, journey_state: 'between_situations', last_completed_position_no: null }), '');
});
test('POSTW02 metadata retains organization and not-started state before a saved plan exists', () => {
  assert.deepEqual(assessmentMetadata({ journey_state: 'preparing', organization_name: 'Synthetic', planned_total: null }), [
    { label: 'Организация', value: 'Synthetic' }, { label: 'Начало оценки', value: 'Оценка ещё не начата' },
  ]);
});
test('POSTW02 metadata follows ready, presented, return, between and result states', () => {
  const card = { ...active, organization_name: 'Synthetic', calendar_deadline: '2026-11-19T12:00:00Z' };
  const org = { label: 'Организация', value: 'Synthetic' };
  assert.deepEqual(assessmentMetadata({ ...card, status: 'prepared', journey_state: 'ready' }), [org, { label: 'План оценки', value: '8 ситуаций' }]);
  for (const journey_state of ['active', 'return_required']) {
    assert.deepEqual(assessmentMetadata({ ...card, journey_state }), [org, { label: 'Текущая ситуация', value: '3 ситуация из 8' }]);
  }
  assert.deepEqual(assessmentMetadata({ ...card, journey_state: 'between_situations', last_completed_position_no: 3 }), [org, { label: 'Текущая ситуация', value: 'Ситуация 3 завершена' }]);
  assert.deepEqual(assessmentMetadata({ ...card, status: 'report_ready', journey_state: 'report_ready', closed_at: '2026-10-17T12:00:00Z' }), [org, { label: 'Дата завершения', value: '17 октября 2026' }]);
});
test('POSTW02 missing position and completion date never invent metadata', () => {
  const org = { label: 'Организация', value: 'Synthetic' };
  assert.deepEqual(assessmentMetadata({ ...active, organization_name: 'Synthetic', current_position_no: null }), [org, { label: 'План оценки', value: '8 ситуаций в плане' }]);
  assert.deepEqual(assessmentMetadata({ status: 'report_ready', planned_total: 8, organization_name: 'Synthetic' }), [org]);
  assert.equal(formatAssessmentDate('invalid'), '');
  assert.equal(formatAssessmentDate(null), '');
  assert.equal(formatAssessmentDate('2026-10-17T22:00:00Z'), '18 октября 2026');
});
