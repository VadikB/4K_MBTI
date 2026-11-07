// Offline integrity/readback check, not a fresh product/browser/provider execution.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../../../..');
const read = async (name) => JSON.parse(await fs.readFile(path.join(directory, name), 'utf8'));
const manifest = await read('FILES.json');
for (const [name, expected] of Object.entries(manifest)) {
  const target = path.resolve(root, name);
  assert.ok(target.startsWith(root + path.sep));
  assert.equal(crypto.createHash('sha256').update(await fs.readFile(target)).digest('hex'), expected, name);
}
const identity = await read('code-identity.json');
assert.equal(identity.main, '946a46cb71e5ca5cc99778f036807d6c193188dc');
assert.equal(identity.implementation, 'c59b024ebfae98790e545eae16d043a2280b9384');
assert.equal(identity.version, '2.0.69');
assert.deepEqual(identity.approved_actions, ['version_bump', 'branch_push', 'pr', 'ci', 'human_review_handoff']);
assert.deepEqual(identity.excluded_actions, ['merge', 'deploy', 'program_publication', 'program_activation', 'working_database', 'paid_llm']);
assert.equal(identity.unchanged_source_comparison, 'PASS');
assert.equal(identity.prep_diag_01_root_cause, 'UNKNOWN');
const browser = await read('browser.json');
assert.equal(browser.stats.expected, 129);
assert.equal(browser.stats.unexpected + browser.stats.skipped + browser.stats.flaky, 0);
assert.deepEqual(browser.errors, []);
const specs = [];
const visit = (suite) => { specs.push(...suite.specs || []); (suite.suites || []).forEach(visit); };
browser.suites.forEach(visit);
for (const [name, count] of [['auth-r03.spec.mjs', 115], ['auth-recovery.spec.mjs', 4], ['program-connection-feedback.spec.mjs', 10]]) {
  assert.equal(specs.filter((spec) => spec.file.endsWith(name)).length, count, name);
}
const runs = specs.flatMap((spec) => spec.tests.flatMap((test) => test.results));
assert.equal(runs.length, 129);
assert.ok(runs.every((run) => run.status === 'passed' && run.retry === 0));
for (const [name, marker] of [['frontend.txt.gz', 'pass 145'], ['release-ci-tests.txt.gz', '22 passed'],
  ['backend.txt.gz', '920 passed'], ['http.txt.gz', '108 passed'],
  ['preflight.txt.gz', 'Ready preflight passed: release 2.0.69'],
  ['preflight-repeat.txt.gz', 'Ready preflight passed: release 2.0.69']]) {
  assert.ok(gunzipSync(await fs.readFile(path.join(directory, 'raw', name))).toString().includes(marker), name);
}
const hashes = await fs.readFile(path.join(directory, 'release-idempotency.sha256'), 'utf8');
assert.equal(hashes.trim().split('\n').length, 49);
assert.ok((await fs.readFile(path.join(root, 'web/js/config.js'), 'utf8')).includes('APP_RELEASE = "2.0.69"'));
process.stdout.write(JSON.stringify({integrity: 'PASS', verified_files: Object.keys(manifest).length,
  scope: 'recorded_results_not_fresh_execution', browser: '129_PASS', frontend: '145_PASS',
  release_ci: '22_PASS', backend: '920_PASS', http: '108_PASS', paid_llm: 0,
  human_review: 'NOT_DONE', merge: false, deploy: false}) + '\n');
