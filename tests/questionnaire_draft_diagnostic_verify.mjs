// Offline evidence consistency only: PASS here never means product/AC18 PASS.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const root = process.cwd();
const directory = path.join(root, 'docs/evc/evidence/ac18-questionnaire-draft-diagnosis');
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests/browser/fixtures/questionnaire-it-synthetic-v1.json')));
const cases = fs.readdirSync(directory).filter((name) => fs.statSync(path.join(directory, name)).isDirectory()).sort();
assert.equal(cases.length, 4);
const seen = new Set();
let defects = 0, controls = 0, files = 0;
const content = [];
for (const name of cases) {
  const caseDirectory = path.join(directory, name);
  const read = (file) => JSON.parse(fs.readFileSync(path.join(caseDirectory, file + '.json')));
  const run = read('run'), result = read('diagnostic-result'), cleanup = read('cleanup');
  const baseline = read('baseline'), before = read('before-release'), after = read('after-release');
  const confirmed = read('confirmed-readback');
  assert(!seen.has(run.run_id)); seen.add(run.run_id);
  assert.equal(run.database, 'product4k_pytest_' + run.run_id);
  assert.equal(run.scope, 'DIAGNOSTIC_NOT_PRODUCT_PASS_NOT_AC18');
  assert.equal(run.provider_mode, 'disabled'); assert.equal(run.gateway, 0);
  assert.equal(cleanup.run_id, run.run_id); assert.equal(cleanup.database, run.database);
  assert.equal(cleanup.owner_verified, true); assert.equal(cleanup.database_absent, true);
  assert.equal(cleanup.state_absent, true); assert.equal(cleanup.force, false);
  for (const db of [baseline, confirmed.database]) {
    assert.equal(db.run_id, run.run_id); assert.equal(db.database, run.database);
    assert.equal(db.owner_verified, true); assert.equal(db.read_only_rollback, true);
  }
  assert.equal(result.diagnostic_status, 'COMPLETED');
  assert.equal(result.provider_operations, 0);
  assert.equal(result.actual_http_postgresql, true); assert.equal(result.real_get_response_unmodified, true);
  assert.equal(result.historical_ac18_causal_identity, 'NOT_PROVEN_NO_HISTORICAL_TIMELINE');
  assert.equal(result.historical_timeout_cleanup_cause, 'UNKNOWN'); assert.equal(result.prep_diag_01, 'UNKNOWN');
  assert.deepEqual(run.scenario, result.scenario);
  for (const [source, expected] of Object.entries(run.source_sha256)) {
    assert.equal(createHash('sha256').update(fs.readFileSync(path.join(root, source))).digest('hex'), expected, source);
  }
  const entered = Object.entries(fixture.fields).slice(0, run.scenario.count);
  for (const [field, value] of entered) assert.equal(before.values[field], value);
  if (run.scenario.count) {
    defects += 1;
    assert.equal(result.product_status, 'FAIL_DRAFT_LOSS_REPRODUCED');
    assert.deepEqual(after.lost_fields, entered.map(([field]) => field));
    for (const [field] of entered) assert.equal(after.values[field], '');
    assert.equal(after.original_node_connected, false);
    const blocked = read('blocked-before-refill');
    assert.equal(blocked.database_readback.run_id, run.run_id);
    assert.equal(blocked.no_preview_post, true); assert.equal(blocked.no_confirm_button, true);
    assert.deepEqual(blocked.database_readback.counts, baseline.counts);
    assert.equal(result.validity_before_refill.valid, false);
    assert(result.validity_before_refill.invalid_fields.some((field) => field.name === 'source_author' && field.value_missing));
  } else {
    controls += 1;
    assert.equal(result.product_status, 'PASS_CONTROL_AFTER_READ_COMPLETE');
    assert.deepEqual(after.lost_fields, []); assert.equal(result.validity_before_refill.valid, true);
  }
  assert.equal(confirmed.http.status, 'confirmed'); assert.equal(confirmed.database.revision.status, 'confirmed');
  assert.equal(confirmed.http.source_author, fixture.fields.source_author);
  assert.equal(confirmed.http.id, confirmed.database.revision.id);
  assert.equal(confirmed.http.assignment_ref, confirmed.database.revision.assignment_ref);
  assert.deepEqual(confirmed.http.answers_json, confirmed.database.revision.answers_json);
  assert.equal(confirmed.database.counts.questionnaire_revisions, baseline.counts.questionnaire_revisions + 1);
  for (const counter of ['assignments', 'profiles', 'preparation_operations', 'cycles', 'assessment_situations', 'assessment_answers']) {
    assert.equal(confirmed.database.counts[counter], baseline.counts[counter]);
    if (counter !== 'profiles') assert.equal(baseline.counts[counter], 0);
  }
  assert(!result.timeline.some((event) => event.event === 'request' && /\/(prepare|start)$/.test(event.path)));
  const first = (event) => result.timeline.findIndex((item) => item.event === event);
  assert(first('real_questionnaire_get_held') < first('before_release'));
  assert(first('before_release') < first('real_questionnaire_get_continued'));
  assert(first('real_questionnaire_get_continued') < first('after_release'));
  assert(result.timeline.some((item) => item.event === 'response' && item.path.endsWith('/questionnaire') && item.status === 200));
  for (const file of fs.readdirSync(caseDirectory).sort()) {
    assert(!['state.json', 'server.log', '.env'].includes(file));
    assert(/\.json$|\.png$/.test(file));
    const bytes = fs.readFileSync(path.join(caseDirectory, file));
    if (file.endsWith('.png')) {
      assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
      assert.equal(bytes.readUInt32BE(16), run.scenario.width);
    }
    content.push([name + '/' + file, createHash('sha256').update(bytes).digest('hex')]);
    files += 1;
  }
}
assert.equal(defects, 3); assert.equal(controls, 1);
console.log(JSON.stringify({ evidence_consistency: 'PASS', files, cases: seen.size,
  product_defect_reproductions: defects, product_control_pass: controls,
  product_fixed: false, ac18: 'BLOCKED_NOT_REPEATED', cleanup_pass: seen.size,
  provider_operations: 0, historical_causality: 'NOT_PROVEN',
  evidence_tree_sha256: createHash('sha256').update(JSON.stringify(content)).digest('hex') }, null, 2));
