// Verify bytes and recorded outcomes, NOT a new acceptance run.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';
import assert from 'node:assert/strict';
const directory = path.dirname(new URL(import.meta.url).pathname);
const root = path.resolve(directory, '../../../..');
const read = async (name) => JSON.parse(await fs.readFile(path.join(directory, name), 'utf8'));
const manifest = await read('FILES.json');
for (const [name, expected] of Object.entries(manifest)) {
  const target = path.resolve(root, name);
  assert.ok(target.startsWith(root + path.sep), name);
  assert.equal(crypto.createHash('sha256').update(await fs.readFile(target)).digest('hex'), expected, name);
}
const diagnosis = await read('diagnosis.json');
const expectedStats = [['current-targeted', 6, 0], ['comparison-targeted', 6, 0],
  ['current-full', 118, 1], ['comparison-status', 0, 3]];
for (const [group, count, failures] of expectedStats) {
  const document = await read(`${group}/results.json`);
  assert.equal(document.stats.expected, count, group);
  assert.equal(document.stats.unexpected, failures, group);
  for (const key of ['flaky', 'skipped']) assert.equal(document.stats[key], 0, group);
  assert.deepEqual(document.errors, [], group);
  let tested = 0;
  const visit = (suite) => {
    for (const spec of suite.specs || []) for (const test of spec.tests) for (const run of test.results) {
      assert.equal(run.retry, 0); tested += 1;
      if (run.status !== 'passed') {
        assert.equal(run.status, 'failed');
        assert.equal(spec.line, 445);
        assert.equal(run.error.location.line, 493);
      }
    }
    (suite.suites || []).forEach(visit);
  };
  document.suites.forEach(visit);
  assert.equal(tested, count + failures);
  assert.equal(document.config.projects[0].timeout, 150000);
}
assert.equal(diagnosis.comparison_commit, 'dea8c44a183c2ac5f4b527e53cdeed0a39bcf454');
assert.equal(diagnosis.product_commit, 'bf637af8e1ee89c1a8d5621c4ce694a52bb0806e');
assert.equal(diagnosis.historical_timeout_root_cause, 'UNKNOWN');
assert.equal(diagnosis.prep_diag_01_root_cause, 'UNKNOWN');
assert.equal(diagnosis.product_changed_by_diagnosis, false);
assert.equal(diagnosis.external_actions, false);
assert.equal(diagnosis.reproduced_timeout, false);
assert.equal(diagnosis.traces.length, 16);
for (const trace of diagnosis.traces) {
  assert.ok(trace.actions.length > 0 && trace.actions.every((action) => action.error === null));
  assert.ok(trace.responses.some((response) => response.path === '/users/session/restore' && response.status === 200));
}
const statusTraces = diagnosis.traces.filter((trace) => ['current-full', 'comparison-status'].includes(trace.group));
assert.equal(statusTraces.length, 4);
for (const trace of statusTraces) {
  assert.ok(trace.expectations.some((check) => check.location.line === 490 && !check.failed));
  assert.ok(trace.expectations.some((check) => check.location.line === 493 && check.failed));
  assert.ok(trace.responses.some((response) => response.path.endsWith('/questionnaire') && response.status === 503));
}
assert.equal(diagnosis.new_defect.preexisting_before_auth_fix, true);
assert.equal(diagnosis.new_defect.product_fix_performed, false);
const oldFailures = diagnosis.historical_failure_actions;
assert.equal(oldFailures.length, 3);
assert.ok(oldFailures[2].errors.some((error) => error.location?.line === 754 && error.message.includes('locator.fill')));
for (const value of Object.values(diagnosis.source_identity)) assert.equal(value.sha256, value.previous_fix_evidence_sha256);
process.stdout.write(JSON.stringify({ integrity: 'PASS', verified_files: Object.keys(manifest).length,
  scope: 'recorded_results_not_fresh_execution', targeted_current: '6_PASS', targeted_comparison: '6_PASS',
  current_full: 'FAIL_118_PASS_1_FAIL', comparison_status_loss: '3_FAIL',
  historical_failures_preserved: true, timeout_root_cause: 'UNKNOWN', new_defect: 'R10-STATUS-DIAG-01',
  product_changed: false, release_authorized: false }) + '\n');
