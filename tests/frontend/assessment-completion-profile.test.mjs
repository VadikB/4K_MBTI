import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { completeStartedAssessment, readExecutionExport, terminalExecutionKnown, destroyOwnedStandIfAdmitted } from '../browser/fixtures/assessment-completion-profile.mjs';

const terminal = { run_id: 'run-1', cycle_id: 'cycle-1', collection_status: 'calculated',
  close_reason: 'route_completed', collection_closed_at: '2026-11-10T10:00:00Z',
  situations: [{ status: 'closed' }], pipeline: { status: 'ready' } };

test('completion readback observes another tab closing the AS before Finish', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-finish-readback-'));
  const ended = { cycle_id: 'cycle-1', status: { collection_status: 'active' },
    current_situation: { assessment_situation_id: 'as-1', status: 'scenario_ended' },
    finish_availability: { allowed: true }, between_situations: false };
  const closed = { ...ended, between_situations: true,
    current_situation: { assessment_situation_id: 'as-1', status: 'closed' } };
  const snapshots = [ended, ended, ended, closed];
  const requests = [];
  const clicks = [];
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
    locator: selector => { throw new Error(`unexpected duplicate Finish: ${selector}`); },
    getByRole: (role, options) => {
      assert.equal(role, 'button');
      assert.equal(options.name, 'Приступить к следующей ситуации');
      return { waitFor: async () => {}, click: async () => { clicks.push('next'); } };
    },
    waitForResponse: async predicate => {
      const receipt = { request: () => ({ method: () => 'POST' }),
        url: () => 'http://fixture.invalid/users/assessment/cycles/cycle-1/next' };
      assert.equal(predicate(receipt), true, 'only explicit Next is permitted');
      requests.push('next');
      return response({ operation_id: 'next-1' });
    },
  };
  try {
    const result = await completeStartedAssessment({ page, base: 'http://fixture.invalid',
      cycleId: 'cycle-1', runId: 'run-1', evidenceDir: dir, initialSituationId: 'as-1',
      stopAfterFirstNext: true,
      onNextAccepted: async () => ({ ownershipChanged: true, nextSituationId: 'as-2' }) });
    assert.deepEqual(clicks, ['next']);
    assert.deepEqual(requests, ['next']);
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
