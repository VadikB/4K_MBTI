// Offline consistency of the free UI fix evidence, never a real-provider AC18.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const root = process.cwd();
const sourceRef = process.argv[2] === '--source-ref' ? process.argv[3] : null;
assert(process.argv.length === 2 || (process.argv.length === 4 && /^[a-f0-9]{40}$/.test(sourceRef || '')));
const sourceBytes = (source) => sourceRef
  ? execFileSync('git', ['show', `${sourceRef}:${source}`], { cwd: root, maxBuffer: 16 * 1024 * 1024 })
  : fs.readFileSync(path.join(root, source));
const directory = path.join(root, 'docs/evc/evidence/ac18-questionnaire-draft-fix/actual-http-pg');
const fixture = JSON.parse(sourceBytes('tests/browser/fixtures/questionnaire-it-synthetic-v1.json'));
const cases = fs.readdirSync(directory).sort();
assert.equal(cases.length, 4);
const runIds = new Set(), scenarios = new Set(), content = [];
for (const name of cases) {
  const caseDirectory = path.join(directory, name);
  const read = (file) => JSON.parse(fs.readFileSync(path.join(caseDirectory, `${file}.json`)));
  const run = read('run'), result = read('result'), cleanup = read('cleanup');
  const before = read('before-release'), after = read('after-release'), baseline = read('baseline');
  const confirmed = read('confirmed-readback'), db = confirmed.database, answers = db.revision.answers_json;
  assert(!runIds.has(run.run_id)); runIds.add(run.run_id); scenarios.add(run.scenario.name);
  assert.equal(run.database, 'product4k_pytest_' + run.run_id);
  assert.equal(run.scope, 'FREE_UI_HTTP_PG_REGRESSION_NOT_AC18');
  assert.equal(run.provider_mode, 'disabled'); assert.equal(run.gateway, 0);
  assert.equal(result.status, 'PASS_UI_HTTP_PG_NOT_AC18');
  assert.deepEqual(result.scenario, run.scenario);
  assert.equal(result.refill_count, 0); assert.equal(result.all_12_after_reload, true);
  assert.equal(result.preview_status, 201); assert.equal(result.confirm_status, 200); assert.equal(result.readback_status, 200);
  assert.equal(result.provider_operations, 0); assert.equal(result.real_get_response_unmodified, true);
  assert.equal(result.historical_ac18_causality, 'NOT_PROVEN');
  assert.equal(result.timeout_cleanup_cause, 'UNKNOWN'); assert.equal(result.prep_diag_01, 'UNKNOWN');
  assert.deepEqual(after.values, before.values); assert.equal(after.original_node_connected, false);
  assert.deepEqual(after.lost_fields, []); assert.equal(before.fields_entered, run.scenario.count);
  assert.equal(result.retained_fields, run.scenario.count);
  for (const [field, value] of Object.entries(fixture.fields).slice(0, run.scenario.count)) {
    assert.equal(before.values[field], value); assert.equal(after.values[field], value);
  }
  for (const record of [baseline, db]) {
    assert.equal(record.run_id, run.run_id); assert.equal(record.database, run.database);
    assert.equal(record.owner_verified, true); assert.equal(record.read_only_rollback, true);
  }
  assert.equal(confirmed.http.status, 'confirmed'); assert.equal(db.revision.status, 'confirmed');
  assert.equal(confirmed.http.id, db.revision.id); assert.equal(confirmed.http.assignment_ref, db.revision.assignment_ref);
  assert.deepEqual(confirmed.http.answers_json, answers);
  assert.deepEqual({ source_author: db.revision.source_author,
    organization_name: answers.C01.name, organization_type: answers.C01.organization_type,
    industry: answers.C01.industry, activity_description: answers.C01.activity_description,
    purpose: answers.C02a.participant_text, results_usage: answers.C03.participant_text,
    result_recipients: answers.C04.answer, organizer: answers.C21.organizer,
    responsible_contact: answers.C21.responsible_contact, case_reality_level: answers.C17.case_reality_level,
    organization_name_usage_rules: answers.C17.organization_name_usage_rules }, fixture.fields);
  assert.deepEqual(db.revision.recipient_mapping_json, ['participant']);
  assert.equal(db.counts.questionnaire_revisions, baseline.counts.questionnaire_revisions + 1);
  for (const counter of ['assignments', 'profiles', 'preparation_operations', 'cycles', 'assessment_situations', 'assessment_answers']) {
    assert.equal(db.counts[counter], baseline.counts[counter]);
    if (counter !== 'profiles') assert.equal(db.counts[counter], 0);
  }
  assert(!result.requests.some((request) => /\/(prepare|start)$/.test(request.path)));
  assert.equal(result.requests.filter((request) => request.method === 'POST' && request.path.endsWith('/questionnaire/preview')).length, 1);
  assert.equal(result.requests.filter((request) => request.method === 'POST' && request.path.endsWith('/confirm')).length, 1);
  assert.equal(cleanup.run_id, run.run_id); assert.equal(cleanup.database, run.database);
  assert.equal(cleanup.owner_verified, true); assert.equal(cleanup.database_absent, true);
  assert.equal(cleanup.state_absent, true); assert.equal(cleanup.force, false);
  for (const [source, expected] of Object.entries(run.source_sha256)) {
    assert.equal(createHash('sha256').update(sourceBytes(source)).digest('hex'), expected, source);
  }
  for (const file of fs.readdirSync(caseDirectory).sort()) {
    assert(!['state.json', 'server.log', '.env'].includes(file)); assert(/\.json$|\.png$/.test(file));
    const bytes = fs.readFileSync(path.join(caseDirectory, file));
    if (file.endsWith('.png')) {
      assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
      assert.equal(bytes.readUInt32BE(16), run.scenario.width);
    }
    content.push([name + '/' + file, createHash('sha256').update(bytes).digest('hex')]);
  }
}
assert.deepEqual([...scenarios].sort(), ['all-fields-1440', 'first-three-1440', 'first-three-390', 'read-complete-control']);
const evidenceRoot = path.dirname(directory);
const browser = JSON.parse(fs.readFileSync(path.join(evidenceRoot, 'browser-summary.json')));
assert.equal(browser.status, 'PASS'); assert.equal(browser.case_count, 140); assert.equal(browser.cases.length, 140);
assert.equal(browser.unexpected, 0); assert.equal(browser.flaky, 0);
assert.deepEqual(browser.groups, { 'adm28-real.spec.mjs': 1, 'auth-r03.spec.mjs': 117,
  'program-connection-feedback.spec.mjs': 10, 'questionnaire-draft-guards.spec.mjs': 7,
  'questionnaire-draft-preservation.spec.mjs': 4, 'questionnaire-it-inputs.spec.mjs': 1 });
for (const item of browser.cases) {
  assert.equal(item.status, 'passed'); assert.equal(item.expected_status, 'passed'); assert.equal(item.attempts, 1);
}
for (const [source, expected] of Object.entries(browser.source_sha256)) {
  assert.equal(createHash('sha256').update(sourceBytes(source)).digest('hex'), expected, source);
}
const supportDirectory = path.join(evidenceRoot, 'it-profile-viewport');
const support = (name) => JSON.parse(fs.readFileSync(path.join(supportDirectory, name + '.json')));
const supportRun = support('run'), supportResult = support('result'), supportCleanup = support('cleanup');
assert.equal(supportResult.status, 'PASS_QUESTIONNAIRE_ONLY');
assert.equal(supportResult.all_12_fields_after_reload, true); assert.equal(supportResult.provider_operations, 0);
assert.deepEqual(support('filled-fields').values, fixture.fields);
assert.deepEqual(support('http-readback').answers_json, support('database-readback').revision.answers_json);
assert.equal(supportCleanup.run_id, supportRun.run_id); assert.equal(supportCleanup.owner_verified, true);
assert.equal(supportCleanup.database_absent, true); assert.equal(supportCleanup.state_absent, true);
assert.equal(supportCleanup.force, false); assert(!runIds.has(supportCleanup.run_id));
const viewports = support('it-questionnaire-viewports');
assert.deepEqual(viewports.map((item) => item.width), [1440, 320, 390, 768]);
for (const viewport of viewports) {
  assert.equal(viewport.document.visibility, 'visible');
  assert(viewport.document.scrollWidth <= viewport.width + 1);
  for (const control of viewport.controls) {
    assert(control.geometry.visible_ratio > 0); assert(control.geometry.box.x >= -1);
    assert(control.geometry.box.x + control.geometry.box.width <= viewport.width + 1);
  }
  const bytes = fs.readFileSync(path.join(supportDirectory, viewport.screenshot));
  assert.equal(bytes.readUInt32BE(16), viewport.width);
}
assert(fs.existsSync(path.join(supportDirectory, 'confirmed-1440.png')));
const adm28Directory = path.join(evidenceRoot, 'existing-adm28');
const adm28Cleanup = JSON.parse(fs.readFileSync(path.join(adm28Directory, 'cleanup.json')));
assert.equal(adm28Cleanup.owner_verified, true); assert.equal(adm28Cleanup.database_absent, true);
assert.equal(adm28Cleanup.state_absent, true); assert.equal(adm28Cleanup.force, false);
assert(!runIds.has(adm28Cleanup.run_id)); assert.notEqual(adm28Cleanup.run_id, supportCleanup.run_id);
for (const width of [1440, 1280, 390, 320]) {
  assert.equal(fs.readFileSync(path.join(adm28Directory, `management-${width}.png`)).readUInt32BE(16), width);
}
console.log(JSON.stringify({ evidence_consistency: 'PASS', source_ref: sourceRef || 'current_worktree',
  cases: runIds.size, primary_files: content.length, ui_http_pg_pass: 4, refill_count: 0,
  browser_pass: 140, supporting_actual_checks: 2, questionnaire_viewport_widths: viewports.map((item) => item.width),
  provider_operations: 0, cleanup_pass: 6, ac18: 'NOT_RUN', historical_causality: 'NOT_PROVEN',
  evidence_tree_sha256: createHash('sha256').update(JSON.stringify(content)).digest('hex') }, null, 2));
