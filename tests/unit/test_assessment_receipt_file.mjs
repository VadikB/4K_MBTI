import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { persistReceipt, isTerminalPreparationReceipt } from '../browser/fixtures/receipt-file.mjs';

test('only a durable terminal preparation receipt permits cleanup', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'p4k-export-'));
  const file = path.join(directory, 'receipt.json');
  const value = { preparation_operation: { status: 'failed', operation_id: 'synthetic' } };
  try {
    assert.equal(isTerminalPreparationReceipt({ preparation_operation: { status: 'running' } }), false);
    assert.equal(isTerminalPreparationReceipt(undefined), false);
    assert.throws(() => persistReceipt(path.join(directory, 'absent', 'receipt.json'), value));
    const digest = persistReceipt(file, value);
    assert.match(digest, /^[a-f0-9]{64}$/);
    assert.deepEqual(JSON.parse(fs.readFileSync(file, 'utf8')), value);
    assert.equal(isTerminalPreparationReceipt(value), true);
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  } finally {
    fs.unlinkSync(file);
    fs.rmdirSync(directory);
  }
});
