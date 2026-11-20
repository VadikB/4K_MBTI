import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { completeStartedAssessment } from '../browser/fixtures/assessment-completion-profile.mjs';

function adapter(mode, dir) {
  const base = 'http://fixture.invalid', cycle = 'cycle-1', as = 'as-1';
  let phase = 'active', question = 0, closed = false, finishAllowed = false, input = '';
  let deliveryPending = false, nextPresented = false;
  const turns = [], events = [], waiters = [];
  const response = (url, payload) => ({ url: () => url, ok: () => true,
    request: () => ({ method: () => 'POST' }), json: async () => structuredClone(payload) });
  const snapshot = () => ({ cycle_id: cycle, current_situation: closed ? null : {
    assessment_situation_id: nextPresented ? 'as-2' : as, status: phase, participant_payload: { introduction: 'fixture' } },
  trace: { turns: structuredClone(turns) },
  status: { collection_status: closed && mode !== 'short_next' ? 'calculated' : 'active' },
  between_situations: mode === 'short_next' && closed,
  ...(mode === 'short_next' && closed ? {
    preparation_operation: { operation_id: 'next-1', status: 'completed' },
    next_presentation: { assessment_situation_id: 'as-2' },
  } : {}),
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
    if (selector === 'next' && mode === 'short_next') {
      nextPresented = true; closed = false; phase = 'active';
      emit(`/users/assessment/m7/cycles/${cycle}/present-next`);
    } else if (selector === '#interview-submit-button') {
      if (question && deliveryPending) throw new Error('UNDELIVERED_ASK_ANSWER');
      turns.push({ speaker_type: 'assessee', content_text: input });
      if (phase === 'active') {
        emit(`/users/assessment/m5/situations/${as}/turns`);
        if (mode === 'other_client_ended') { phase = 'scenario_ended'; finishAllowed = true; events.push('other_client_end'); }
      } else {
        emit(`/users/assessment/m7/clarifications/q${question}/answers`);
        if (mode === 'ask_loop') question = question === 1 ? 2 : 1;
        else if (mode === 'second_ask' && question === 1) question = 2;
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
    click: () => click(selector), waitFor: async () => {}, filter: () => locator(selector), or: () => locator(selector) });
  const page = { request: { get: async (url) => response(url,
    url.includes('/runtime') ? snapshot() : url.includes('/execution-export/') ? exported()
      : url.includes('/journey-state') ? { report_status: closed ? 'ready' : 'waiting' }
        : { id: 'report-1', cycle_id: cycle, owner_user_id: 501, status: 'ready', audience: 'assessee',
          results_revision_id: 'results-1', revision_no: 1 }) },
  locator, getByRole: () => locator(mode === 'short_next' ? 'next' : 'report-open'), evaluate: async () => 501, goto: async () => {},
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

for (const [limits, reason] of [
  [{ maxStepsPerAS: 5, maxSteps: 100 }, /DRIVER_AS_STEP_LIMIT/],
  [{ maxStepsPerAS: 100, maxSteps: 6 }, /DRIVER_RUN_STEP_LIMIT/],
]) {
  test(`actual ASK-loop stops with ${reason}`, async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-limits-'));
    const { page, events, waiters } = adapter('ask_loop', dir);
    try {
      await assert.rejects(completeStartedAssessment({ page, base: 'http://fixture.invalid',
        cycleId: 'cycle-1', runId: 'run-1', evidenceDir: dir, initialSituationId: 'as-1',
        maxSituations: 2, limits }), reason);
      const answers = events.filter(x => x.includes('/answers')).length;
      console.log(JSON.stringify({ limits, reason: String(reason), accepted_ask_answers: answers, as_count: 1 }));
      assert.equal(answers, 3);
      assert.equal(events.filter(x => x.includes('/finish-situation')).length, 0);
      assert.equal(events.filter(x => x.includes('/next')).length, 0);
    } finally {
      for (const waiter of waiters) clearTimeout(waiter.timer);
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
}

for (const [limits, reason] of [
  [{ deadlineMs: 80, noProgressMs: 1000 }, /RUN_DEADLINE_EXCEEDED/],
  [{ deadlineMs: 1000, noProgressMs: 80 }, /RUN_NO_PROGRESS_EXCEEDED/],
]) {
  test(`actual driver unchanged processing stops with ${reason}`, async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-stalled-'));
    let heartbeat = 0, commands = 0;
    const page = { on: () => {}, request: { get: async () => ({ ok: () => true,
      json: async () => ({ cycle_id: 'cycle-1', status: { collection_status: 'active' },
        current_situation: { assessment_situation_id: 'as-1', status: 'scenario_ended' },
        pipeline: { status: 'processing', heartbeat: ++heartbeat } }) }) },
    waitForTimeout: () => new Promise(resolve => setTimeout(resolve, 5)),
    locator: () => { commands++; throw Error('UNEXPECTED_COMMAND'); } };
    try {
      const started = Date.now();
      await assert.rejects(completeStartedAssessment({ page, base: 'http://fixture.invalid',
        cycleId: 'cycle-1', runId: 'run-1', evidenceDir: dir, initialSituationId: 'as-1', limits }), reason);
      assert.ok(Date.now() - started < 1000);
      assert.ok(heartbeat > 2);
      assert.equal(commands, 0);
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  });
}

test('short positive driver stops at explicit Next within finite limits, before Report', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-short-'));
  const { page, events, waiters } = adapter('short_next', dir);
  const original = page.request.get;
  page.request.get = async url => {
    assert.ok(!url.includes('journey-state') && !url.includes('/reports/'));
    return original(url);
  };
  try {
    const result = await completeStartedAssessment({ page, base: 'http://fixture.invalid',
      cycleId: 'cycle-1', runId: 'run-1', evidenceDir: dir, initialSituationId: 'as-1',
      maxSituations: 2, limits: { maxSteps: 12, maxStepsPerAS: 10 }, stopAfterFirstNext: true });
    assert.equal(result.contract, 'assessment-first-next/1');
    assert.equal(result.next_assessment_situation_id, 'as-2');
    assert.equal(events.filter(x => x.endsWith('/present-next')).length, 1);
  } finally {
    for (const waiter of waiters) clearTimeout(waiter.timer);
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
