import test from 'node:test';
import assert from 'node:assert/strict';
import { assessmentPositionText } from '../../web/js/dashboard-presentation.js';
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
