import assert from 'node:assert/strict';
import test from 'node:test';
import { waitForProductCyclePreparation } from '../../web/js/product-cycle-preparation.js';

test('F09 local wait limit preserves queued operation identity and never reports server failure', async () => {
  const accepted = { operation_id: 'synthetic-next-1', status: 'queued' };
  await assert.rejects(waitForProductCyclePreparation(accepted, { maxWaitMs: 0 }), (error) => {
    assert.equal(error.name, 'PreparationWaitLimit');
    assert.equal(error.operationId, accepted.operation_id);
    assert.equal(error.operationStatus, 'queued');
    assert.notEqual(error.name, 'PreparationFailed');
    return true;
  });
});

test('F09 terminal worker result retains server retry permission', async () => {
  const failed = { operation_id: 'synthetic-next-2', status: 'failed',
    retry_allowed: false, error: { message: 'synthetic worker refusal' } };
  await assert.rejects(waitForProductCyclePreparation(failed, { maxWaitMs: 0 }), (error) => {
    assert.equal(error.name, 'PreparationFailed');
    assert.equal(error.retryAllowed, false);
    return true;
  });
  const complete = { operation_id: 'synthetic-next-3', status: 'completed', result: { decision: { status: 'SELECTED' } } };
  assert.equal((await waitForProductCyclePreparation(complete, { maxWaitMs: 0 })).decision.status, 'SELECTED');
});
