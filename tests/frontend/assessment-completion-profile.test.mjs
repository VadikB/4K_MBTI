import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { readExecutionExport, terminalExecutionKnown } from '../browser/fixtures/assessment-completion-profile.mjs';

const terminal = { run_id: 'run-1', cycle_id: 'cycle-1', collection_status: 'calculated',
  close_reason: 'route_completed', collection_closed_at: '2026-11-10T10:00:00Z',
  situations: [{ status: 'closed' }], pipeline: { status: 'ready' } };

test('cleanup requires a known terminal execution outcome after preparation', () => {
  assert.equal(terminalExecutionKnown(terminal), true);
  assert.equal(terminalExecutionKnown({ ...terminal, pipeline: { status: 'failed' } }), true);
  assert.equal(terminalExecutionKnown({ ...terminal, situations: [{ status: 'active' }] }), false);
  assert.equal(terminalExecutionKnown({ ...terminal, collection_status: 'active' }), false);
  assert.equal(terminalExecutionKnown({ ...terminal, pipeline: { status: 'processing' } }), false);
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
