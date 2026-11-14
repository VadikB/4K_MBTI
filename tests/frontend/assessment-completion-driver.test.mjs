import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { completeStartedAssessment } from '../browser/fixtures/assessment-completion-profile.mjs';

function adapter(mode, dir) {
  const base = 'http://fixture.invalid', cycle = 'cycle-1', as = 'as-1';
  let phase = 'active', question = 0, closed = false, finishAllowed = false, input = '';
  let deliveryPending = false;
  const turns = [], events = [], waiters = [];
  const response = (url, payload) => ({ url: () => url, ok: () => true,
    request: () => ({ method: () => 'POST' }), json: async () => structuredClone(payload) });
  const snapshot = () => ({ cycle_id: cycle, current_situation: closed ? null : {
    assessment_situation_id: as, status: phase, participant_payload: { introduction: 'fixture' } },
  trace: { turns: structuredClone(turns) },
  status: { collection_status: closed ? 'calculated' : 'active' }, between_situations: false,
  clarification: question ? { id: `q${question}`, status: 'ASK', question_turn_id: deliveryPending ? null : `q${question}`,
    response_outcome: null } : null, finish_availability: { allowed: finishAllowed } });
  const exported = () => ({ run_id: 'run-1', cycle_id: cycle, owner_user_id: 501,
    collection_status: closed ? 'calculated' : 'active', close_reason: closed ? 'route_completed' : null,
    collection_closed_at: closed ? '2026-11-10T10:00:00Z' : null,
    situations: [{ assessment_situation_id: as, session_id: 'session-1', status: closed ? 'closed' : phase,
      final_handoff_id: closed ? 'handoff-1' : null, finalization_status: closed ? 'queued' : null,
      assessee_turns: turns.length,
      interim_handoffs: question ? 1 : 0, c54_receipts: question ? 1 : 0 }],
    c46: closed ? { id: 'c46-1' } : null,
    pipeline: closed ? { status: 'ready', latest_report_id: 'report-1',
      latest_results_revision_id: 'results-1' } : null,
    results: closed ? { id: 'results-1', c46_revision_id: 'c46-1' } : null,
    report: closed ? { id: 'report-1', status: 'ready', audience: 'assessee', revision_no: 1,
      created_by: 501, result_revision_id: 'results-1' } : null });
  const emit = (endpoint) => {
    events.push(endpoint);
    for (const waiter of [...waiters]) {
      const result = response(base + endpoint, {});
      if (waiter.predicate(result)) {
        clearTimeout(waiter.timer); waiters.splice(waiters.indexOf(waiter), 1); waiter.resolve(result);
      }
    }
  };
  const click = async (selector) => {
    if (selector === '#interview-submit-button') {
      if (question && deliveryPending) throw new Error('UNDELIVERED_ASK_ANSWER');
      turns.push({ speaker_type: 'assessee', content_text: input });
      if (phase === 'active') {
        emit(`/users/assessment/m5/situations/${as}/turns`);
        if (mode === 'other_client_ended') { phase = 'scenario_ended'; finishAllowed = true; events.push('other_client_end'); }
      } else {
        emit(`/users/assessment/m7/clarifications/q${question}/answers`);
        if (mode === 'second_ask' && question === 1) question = 2;
        else { question = 0; finishAllowed = true; }
      }
    } else if (selector === '#interview-finish-button' && phase === 'active') {
      phase = 'scenario_ended'; emit(`/users/assessment/m5/situations/${as}/transitions`);
      if (mode === 'calendar_close') closed = true;
      else {
        question = 1;
        deliveryPending = ['delayed_ask', 'undelivered_ask'].includes(mode);
      }
    } else if (selector === '#interview-finish-button') {
      closed = true; emit(`/users/assessment/m7/cycles/${cycle}/finish-situation`);
    }
  };
  const locator = (selector) => ({ fill: async (text) => { input = text; },
    click: () => click(selector), waitFor: async () => {} });
  const page = { request: { get: async (url) => response(url,
    url.includes('/runtime') ? snapshot() : url.includes('/execution-export/') ? exported()
      : url.includes('/journey-state') ? { report_status: closed ? 'ready' : 'waiting' }
        : { id: 'report-1', cycle_id: cycle, owner_user_id: 501, status: 'ready', audience: 'assessee',
          results_revision_id: 'results-1', revision_no: 1 }) },
  locator, getByRole: () => locator('report-open'), evaluate: async () => 501, goto: async () => {},
  on: () => {},
  waitForTimeout: async () => {
    if (mode === 'undelivered_ask' && deliveryPending) throw new Error('CONTROLLED_DELIVERY_DEADLINE');
    if (deliveryPending) { deliveryPending = false; events.push('ask_delivered'); }
  }, screenshot: async ({ path: file }) => fs.writeFileSync(file, 'fixture image'),
  waitForResponse: (predicate) => new Promise((resolve, reject) => {
    const waiter = { predicate, resolve, timer: setTimeout(() => reject(Error('UNEXPECTED_POST_WAIT')), 300) };
    waiters.push(waiter);
  }) };
  return { page, events, waiters };
}

for (const mode of ['one_ask', 'second_ask', 'other_client_ended', 'calendar_close', 'delayed_ask']) {
  test(`driver accepts ${mode} and does not send a stale command`, async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-exec-driver-'));
    const { page, events, waiters } = adapter(mode, dir);
    try {
      const receipt = await completeStartedAssessment({ page, base: 'http://fixture.invalid',
        cycleId: 'cycle-1', runId: 'run-1', evidenceDir: dir, initialSituationId: 'as-1', maxSituations: 2 });
      assert.equal(receipt.contract, 'assessment-execution-contour/2');
      assert.equal(receipt.stages.at(-1).stage, 'report_opened');
      if (mode === 'second_ask') assert.equal(events.filter((value) => value.includes('/answers')).length, 2);
      if (mode === 'other_client_ended') assert.equal(events.filter((value) => value.includes('/transitions')).length, 0);
      if (mode === 'calendar_close') assert.equal(events.filter((value) => value.includes('/finish-situation')).length, 0);
      if (mode === 'delayed_ask') {
        assert.equal(events.filter((value) => value.includes('/answers')).length, 1);
        assert.ok(events.indexOf('ask_delivered') < events.findIndex((value) => value.includes('/answers')));
      }
    } finally {
      for (const waiter of waiters) clearTimeout(waiter.timer);
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
}

test('driver never answers an ASK that remains undelivered', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-exec-driver-'));
  const { page, events, waiters } = adapter('undelivered_ask', dir);
  try {
    await assert.rejects(completeStartedAssessment({ page, base: 'http://fixture.invalid',
      cycleId: 'cycle-1', runId: 'run-1', evidenceDir: dir, initialSituationId: 'as-1', maxSituations: 2 }),
    /CONTROLLED_DELIVERY_DEADLINE/);
    assert.equal(events.filter((value) => value.includes('/answers')).length, 0);
    assert.equal(events.filter((value) => value.includes('/finish-situation')).length, 0);
  } finally {
    for (const waiter of waiters) clearTimeout(waiter.timer);
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
