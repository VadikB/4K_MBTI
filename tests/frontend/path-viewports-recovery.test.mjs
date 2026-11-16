import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { capturePathViewports } from '../browser/fixtures/path-viewports.mjs';

for (const restoreFails of [false, true]) test(`viewport evidence preserves primary failure and restoration policy (${restoreFails})`, async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'p4k-viewports-'));
  const original = { width: 390, height: 844 };
  const failure = new Error('SYNTHETIC_GEOMETRY_FAILURE');
  const changes = [];
  const page = { viewportSize: () => original, bringToFront: async () => {},
    setViewportSize: async (value) => {
      changes.push(value);
      if (restoreFails && value === original) throw new Error('SYNTHETIC_RESTORE_FAILURE');
    },
    evaluate: async () => { throw failure; }, screenshot: async () => {},
  };
  try {
    await assert.rejects(capturePathViewports(page, directory, 'failure', [], { widths: [1440] }),
      (error) => error === failure);
    assert.deepEqual(changes, [{ width: 1440, height: 1000 }, original]);
    const records = JSON.parse(await fs.readFile(path.join(directory, 'failure-viewports.json'), 'utf8'));
    assert.equal(records[0].error, 'VIEWPORT_ASSERTION_FAILED');
  } finally { await fs.rm(directory, { recursive: true, force: true }); }
});
