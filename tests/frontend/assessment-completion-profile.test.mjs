import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { completeStartedAssessment, readExecutionExport, terminalExecutionKnown, destroyOwnedStandIfAdmitted } from '../browser/fixtures/assessment-completion-profile.mjs';

const terminal = { run_id: 'run-1', cycle_id: 'cycle-1', collection_status: 'calculated',
  close_reason: 'route_completed', collection_closed_at: '2026-11-10T10:00:00Z',
  situations: [{ status: 'closed' }], pipeline: { status: 'ready' } };

for (const closure of ['before', 'after', 'unconfirmed']) test(`completion requires confirmed AS closure: ${closure} the last Finish read`, async () => {
  const closesAfterRead = closure !== 'before';
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-finish-readback-'));
  const ended = { cycle_id: 'cycle-1', status: { collection_status: 'active' },
    current_situation: { assessment_situation_id: 'as-1', status: 'scenario_ended' },
    finish_availability: { allowed: true }, between_situations: false };
  const closed = { ...ended, between_situations: true,
    current_situation: { assessment_situation_id: 'as-1', status: 'closed' },
    preparation_operation: { operation_id: 'next-1', status: 'completed' } };
  const ready = { ...closed, next_presentation: { assessment_situation_id: 'as-2' } };
  const presented = { ...ended, current_situation: { assessment_situation_id: 'as-2', status: 'active', participant_payload: {} } };
  const snapshots = closure === 'unconfirmed' ? [ended, ended, ended, ended, ended]
    : closesAfterRead ? [ended, ended, ended, ended, closed, closed, closed, ready, presented]
      : [ended, ended, ended, closed, closed, ready, presented];
  const requests = [];
  const clicks = [];
  let finishAttempts = 0;
  const response = value => ({ ok: () => true, json: async () => value });
  const page = {
    acceptanceDialogHandler: true,
    request: { get: async url => {
      if (url.endsWith('/runtime')) {
        assert.ok(snapshots.length, 'unexpected extra runtime read');
        return response(snapshots.shift());
      }
      assert.ok(url.endsWith('/__pytest__/execution-export/cycle-1'));
      return response({ situations: [{ assessment_situation_id: 'as-1', status: 'closed',
        session_id: 'session-1', final_handoff_id: 'handoff-1', finalization_status: 'ready' }] });
    } },
    locator: selector => {
      assert.equal(selector, '#interview-finish-button');
      assert.equal(closesAfterRead, true, 'no Finish attempt after an already closed readback');
      return { click: async () => { finishAttempts += 1; throw new Error('synthetic hidden Finish'); } };
    },
    getByRole: (role, options) => {
      assert.equal(role, 'button');
      assert.equal(options.name, 'Приступить к следующей ситуации');
      return { waitFor: async () => {}, click: async () => { clicks.push('next'); } };
    },
    waitForResponse: async predicate => {
      const finish = { request: () => ({ method: () => 'POST' }),
        url: () => 'http://fixture.invalid/users/assessment/cycles/cycle-1/finish-situation' };
      if (predicate(finish)) throw new Error('no local Finish receipt after another tab closed the AS');
      const receipt = { request: () => ({ method: () => 'POST' }),
        url: () => 'http://fixture.invalid/users/assessment/cycles/cycle-1/present-next' };
      assert.equal(predicate(receipt), true, 'only explicit presentation is permitted');
      requests.push('next');
      return response({ operation_id: 'next-1' });
    },
  };
  try {
    const completion = completeStartedAssessment({ page, base: 'http://fixture.invalid',
      cycleId: 'cycle-1', runId: 'run-1', evidenceDir: dir, initialSituationId: 'as-1',
      stopAfterFirstNext: true });
    if (closure === 'unconfirmed') {
      await assert.rejects(completion, /synthetic hidden Finish/);
      assert.deepEqual(clicks, []);
      assert.deepEqual(requests, []);
      assert.equal(finishAttempts, 1);
      assert.equal(snapshots.length, 0);
      return;
    }
    const result = await completion;
    assert.deepEqual(clicks, ['next']);
    assert.deepEqual(requests, ['next']);
    assert.equal(finishAttempts, closesAfterRead ? 1 : 0);
    assert.equal(snapshots.length, 0);
    assert.equal(result.stages[1].assessment_situation_id, 'as-1');
    assert.equal(result.stages[1].close_status, 'closed');
    assert.equal(result.next_assessment_situation_id, 'as-2');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('cleanup requires a known terminal execution outcome after preparation', () => {
  assert.equal(terminalExecutionKnown(terminal), true);
  assert.equal(terminalExecutionKnown({ ...terminal, pipeline: { status: 'failed' } }), true);
  assert.equal(terminalExecutionKnown({ ...terminal, situations: [{ status: 'active' }] }), false);
  assert.equal(terminalExecutionKnown({ ...terminal, collection_status: 'active' }), false);
  assert.equal(terminalExecutionKnown({ ...terminal, pipeline: { status: 'processing' } }), false);
});

test('coordinator preserves owned DB when execution export is missing', () => {
  const actions = [];
  const options = { executionStarted: true, terminalExecutionExportSaved: false,
    preparationReceiptRequired: true, terminalPreparationReceiptSaved: true,
    runId: 'run-1', statePath: 'owned-state',
    save: (kind) => actions.push(kind), cli: (action) => actions.push(action) };
  assert.throws(() => destroyOwnedStandIfAdmitted(options), /Cleanup deferred/);
  assert.deepEqual(actions, []);
  destroyOwnedStandIfAdmitted({ ...options, terminalExecutionExportSaved: true });
  assert.deepEqual(actions, ['destroy']);
});

test('terminal export is persisted and checked before cleanup admission', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-exec-export-'));
  try {
    const page = { request: { get: async () => ({ ok: () => true, json: async () => terminal }) } };
    const saved = await readExecutionExport(page, 'http://localhost', 'cycle-1', 'run-1', dir);
    assert.equal(saved.file, 'terminal-execution-export.json');
    assert.equal(saved.value.run_id, 'run-1');
    assert.equal(fs.existsSync(path.join(dir, saved.file)), true);
    await assert.rejects(readExecutionExport(page, 'http://localhost', 'cycle-1', 'foreign', dir),
      /EXECUTION_EXPORT_CONTEXT_MISMATCH/);
    const broken = { request: { get: async () => ({ ok: () => false, status: () => 503 }) } };
    await assert.rejects(readExecutionExport(broken, 'http://localhost', 'cycle-1', 'run-1', dir),
      /execution export: HTTP 503/);
    await assert.rejects(readExecutionExport(page, 'http://localhost', 'cycle-1', 'run-1', dir, 'write'),
      /INJECTED_EXECUTION_EXPORT_WRITE_FAILURE/);
    await assert.rejects(readExecutionExport(page, 'http://localhost', 'cycle-1', 'run-1', dir, 'readback'),
      /EXECUTION_EXPORT_READBACK_MISMATCH/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

for (const fault of ['write', 'readback']) {
  test(`export ${fault} retains actual file state and diagnostic error`, async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-retain-'));
    const file = path.join(dir, 'state.json');
    const state = { run_id: 'run-1', database: 'product4k_pytest_file_fixture', collection_status: 'active' };
    fs.writeFileSync(file, JSON.stringify(state));
    const commands = [];
    let scenarioOutcome = 'controlled_target_completed';
    try {
      const page = { request: { get: async () => ({ ok: () => true, json: async () => terminal }) } };
      await assert.rejects(readExecutionExport(page, 'http://fixture.invalid', 'cycle-1', 'run-1', dir, fault),
        /EXECUTION_EXPORT/);
      assert.throws(() => destroyOwnedStandIfAdmitted({ executionStarted: true,
        terminalExecutionExportSaved: false, preparationReceiptRequired: true,
        terminalPreparationReceiptSaved: true, statePath: file, runId: 'run-1',
        save: (name, value) => fs.writeFileSync(path.join(dir, name + '.json'), JSON.stringify(value)),
        cli: action => commands.push(action) }), /Cleanup deferred/);
      assert.deepEqual(commands, []);
      assert.deepEqual(JSON.parse(fs.readFileSync(file, 'utf8')), state);
      if (fault === 'readback') assert.match(fs.readFileSync(path.join(dir, 'terminal-execution-export.json'), 'utf8'), /corrupted readback/);
      assert.equal(scenarioOutcome, 'controlled_target_completed');
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  });
}
