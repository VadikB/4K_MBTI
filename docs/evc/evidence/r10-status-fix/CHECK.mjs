// Offline verification of recorded evidence; no product/browser/DB/provider run.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { gunzipSync } from 'node:zlib';
const directory = path.dirname(new URL(import.meta.url).pathname);
const root = path.resolve(directory, '../../../..');
const read = async (name) => JSON.parse(await fs.readFile(path.join(directory, name), 'utf8'));
const manifest = await read('FILES.json');
for (const [name, expected] of Object.entries(manifest)) {
  const target = path.resolve(root, name);
  assert.ok(target.startsWith(root + path.sep));
  assert.equal(crypto.createHash('sha256').update(await fs.readFile(target)).digest('hex'), expected, name);
}
function specs(document) {
  const found = [];
  const visit = (suite) => { found.push(...suite.specs || []); (suite.suites || []).forEach(visit); };
  document.suites.forEach(visit); return found;
}
for (const [group, expected, unexpected] of [['before', 0, 1], ['targeted', 10, 0], ['full', 129, 0]]) {
  const document = await read(`${group}/results.json`);
  assert.equal(document.stats.expected, expected, group);
  assert.equal(document.stats.unexpected, unexpected, group);
  assert.equal(document.stats.skipped + document.stats.flaky, 0, group);
  assert.deepEqual(document.errors, [], group);
  const runs = specs(document).flatMap((spec) => spec.tests.flatMap((test) => test.results));
  assert.equal(runs.length, expected + unexpected);
  assert.ok(runs.every((run) => run.retry === 0));
  assert.equal(runs.filter((run) => run.status === 'passed').length, expected);
  if (group === 'before') {
    assert.equal(runs[0].status, 'failed');
    assert.equal(runs[0].error.location.line, 99);
  }
}
const full = await read('full/results.json');
for (const [file, count] of [['auth-r03.spec.mjs', 115], ['auth-recovery.spec.mjs', 4], ['program-connection-feedback.spec.mjs', 10]]) {
  assert.equal(specs(full).filter((spec) => spec.file.endsWith(file)).length, count, file);
}
for (const [name, text] of [['frontend.tap.gz', 'pass 145'], ['backend.txt.gz', '920 passed'], ['http.txt.gz', '108 passed']]) {
  assert.ok(gunzipSync(await fs.readFile(path.join(directory, name))).toString().includes(text), name);
}
const identity = await read('code-identity.json');
assert.equal(identity.base, '4f2e884eac9e00f6f169dddfe5fad6d7a910aaa9');
assert.deepEqual(identity.runtime_sources_changed, ['web/js/screens/admin/organizations.js']);
assert.equal(identity.exact_readback_comparator_unchanged, true);
assert.equal(identity.version, '2.0.68');
assert.equal(identity.timeout_root_cause, 'UNKNOWN');
assert.equal(identity.prep_diag_01_root_cause, 'UNKNOWN');
assert.ok(Object.values(identity.external_actions).every((value) => value === false));
process.stdout.write(JSON.stringify({ integrity: 'PASS', verified_files: Object.keys(manifest).length,
  scope: 'recorded_results_not_fresh_execution', before: 'FAIL_REPRODUCED', targeted: '10_PASS',
  browser: '129_PASS', frontend: '145_PASS', backend: '920_PASS', http: '108_PASS',
  timeout_root_cause: 'UNKNOWN', prep_root_cause: 'UNKNOWN', release_authorized: false }) + '\n');
