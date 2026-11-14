import assert from 'node:assert/strict';
import test from 'node:test';
import { createInterviewHarness } from './helpers/p3-a-interview.mjs';

test('F18 pending entry discards local placeholder progress and time until server readback', () => {
  const h = createInterviewHarness({ meta: true });
  Object.assign(h.state, { assessmentCaseNumber: 1, assessmentTotalCases: 5, assessmentRemainingSeconds: 7200 });
  h.subject.openInterview();
  assert.equal(h.badge.textContent, 'Прогресс уточняется');
  assert.equal(h.timer.textContent, 'Время уточняется');
});

for (const completed of [undefined, null, '0']) {
  test(`F18 missing or invalid completed count ${String(completed)} stays unknown`, () => {
    const h = createInterviewHarness({ meta: true });
    const saved = h.snapshot();
    saved.route.progress = { total_positions: 8, completed_positions: completed };
    h.subject.renderProductRuntime(saved);
    assert.equal(h.badge.textContent, 'Прогресс уточняется');
  });
}

for (const total of [8, 3]) {
  test(`F18 return card and header share frozen plan${total}, completed0 and confirmed pause`, () => {
    const h = createInterviewHarness({ meta: true });
    h.subject.renderReturnCard({ cycle_id: 'cycle-a', current_assessment_situation_id: 'as-a',
      position_no: 1, collection_status: 'active', allowed_action: 'continue_current', remaining_seconds: 123,
      progress: { total_positions: total, completed_positions: 0 } });
    assert.equal(h.badge.textContent, `Ситуация 1 из ${total}\nЗавершено 0 из ${total}`);
    assert.match(h.messages.firstChild.children[1].textContent, new RegExp(`Завершено 0 из ${total}`));
    assert.equal(h.timer.textContent, 'Пауза · 02:03');
  });
  test(`F18 frozen plan${total}, catalog9, materialized1: current and completed use server facts`, () => {
    const h = createInterviewHarness({ meta: true });
    const saved = h.snapshot();
    saved.plan = { catalog: Array.from({ length: 9 }), route: Array.from({ length: total }) };
    saved.route = { positions: [{ position_no: 1, current_assessment_situation_id: 'as-a', state: 'in_progress' }],
      progress: { total_positions: total, completed_positions: 0 } };
    h.subject.renderProductRuntime(saved);
    assert.equal(h.badge.textContent, `Ситуация 1 из ${total}\nЗавершено 0 из ${total}`);
    // The current position never implies that all earlier positions completed.
    saved.route.positions[0].position_no = 3;
    saved.route.progress.completed_positions = 1;
    h.subject.renderProductRuntime(saved);
    assert.equal(h.badge.textContent, `Ситуация 3 из ${total}\nЗавершено 1 из ${total}`);
    assert.equal(h.context.interviewProgressFill.style.width, Math.round(100 / total) + '%');
  });
}

for (const remaining of [120, 0, null, undefined, -1, '0', NaN, Infinity]) {
  test(`F19 Cycle time ${String(remaining)} never falls back to stale legacy fields`, () => {
    const h = createInterviewHarness({ meta: true });
    h.state.assessmentCaseStartedAt = '2000-01-01T00:00:00Z';
    h.state.assessmentTimeLimitMinutes = 60;
    const saved = h.snapshot();
    saved.status.remaining_seconds = remaining;
    h.subject.renderProductRuntime(saved);
    assert.equal(h.timer.textContent, remaining === 120 ? '02:00' : remaining === 0 ? '00:00' : 'Время уточняется');
    assert.equal(h.timer.classList.contains('is-paused'), false);
  });
}

test('F19 known legacy timer remains compatible outside Cycle runtime', () => {
  const h = createInterviewHarness({ meta: true });
  h.state.assessmentRuntimeKind = 'legacy';
  h.state.productCycleId = null;
  h.state.assessmentRemainingSeconds = null;
  h.state.assessmentCaseStartedAt = new Date(Date.now() - 1000).toISOString();
  h.state.assessmentTimeLimitMinutes = 60;
  assert.ok(h.subject.getRemainingCaseTimeMs() > 3500000);
});
