// Offline audit of one NEGATIVE diagnostic. Never a replacement for PATH acceptance.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../..');
const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const fileHash = p => createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const canonical = x => Array.isArray(x) ? '[' + x.map(canonical).join(',') + ']'
  : x && typeof x === 'object' ? '{' + Object.keys(x).sort().map(k => JSON.stringify(k) + ':' + canonical(x[k])).join(',') + '}'
    : JSON.stringify(x);
const objectHash = x => createHash('sha256').update(canonical(x) + '\n').digest('hex');
const sourceCode = '2dc98c6b5b2637c6c505a90686e82f5e4274e763';
const identity = read(path.join(here, 'code-identity.json'));
assert.equal(identity.sha, sourceCode);
assert.equal(identity.worktree_status, '');
for (const [p, h] of Object.entries(identity.files)) assert.equal(fileHash(path.join(root, p)), h, p);
const manifestFile = path.join(root, 'MANIFEST.json');
if (fs.existsSync(manifestFile)) {
  for (const [p, h] of Object.entries(read(manifestFile).files)) assert.equal(fileHash(path.join(root, p)), h, p);
}
const run = read(path.join(here, 'run/run.json'));
const receipt = read(path.join(here, 'run/source-to-runtime-receipt.json'));
const failure = read(path.join(here, 'run/failure.json'));
const cleanup = read(path.join(here, 'run/cleanup.json'));
const completion = read(path.join(here, 'run/completion.json'));
const process = read(path.join(here, 'run/process-result.json'));
const summary = read(path.join(here, 'runner-result.json'));
const lifecycle = read(path.join(here, 'lifecycle-audit.json'));
assert.equal(run.run_id, '96abd1c7e28e4316bcceb069520273e6');
assert.equal(run.database, 'product4k_pytest_' + run.run_id);
for (const row of [cleanup, completion, process]) assert.equal(row.run_id, run.run_id);
assert.equal(cleanup.database, run.database);
for (const k of ['owner_verified', 'database_absent', 'state_absent']) assert.equal(cleanup[k], true);
assert.equal(cleanup.force, false);
assert.equal(process.exit_code, 1);
assert.equal(completion.status, 'failed');
assert.equal(summary.result, 'FAIL');
assert.equal(summary.runs.length, 1);
assert.equal(summary.runs[0].result, 'FAIL');
assert.equal(summary.runs[0].provider_completed_requests, 10);
assert.match(failure.actual, /PLAN_NOT_READY/);
assert.equal(receipt.plan.status, 'LIMITED');
assert.equal(receipt.preparation_operation.status, 'completed');
const { verifyPreparation } = await import(path.join(root, 'tests/browser/fixtures/preparation-receipt.mjs'));
assert.throws(() => verifyPreparation(receipt), e => e.message.includes('PLAN_NOT_READY'));
const generated = receipt.functional_generation;
assert.equal(generated.admission_status, 'PASS');
assert.equal(generated.admitted_for_participant, true);
assert.equal(receipt.assessment_situation.status, 'admitted');
assert.equal(generated.repair_used, false);
assert.equal(generated.candidate_ref.case_id, receipt.saved_checksums.case_ref.id);
assert.equal(generated.candidate_ref.case_version, receipt.saved_checksums.case_ref.version);
assert.equal(generated.stages.generation.operation_id, generated.final_generation_operation_id);
assert.equal(generated.calls.find(c => c.operation_id === generated.final_generation_operation_id)?.kind, 'generation');
for (const [a, b] of [
  [generated.candidate_checksum, generated.candidate_recomputed_checksum],
  [generated.candidate_checksum, generated.candidate_ref.checksum],
  [generated.compiled_case_checksum, receipt.saved_checksums.case_ref.checksum],
  [receipt.assessment_situation.snapshot_checksum, receipt.saved_checksums.snapshot_recomputed],
  [receipt.saved_checksums.execution_payload_ref.checksum, receipt.saved_checksums.execution_payload_recomputed],
]) { assert.match(a, /^[a-f0-9]{64}$/); assert.equal(a, b); }
assert.equal(generated.calls.length, 10);
assert.equal(new Set(generated.calls.map(c => c.operation_id)).size, 10);
assert.equal(generated.calls.flatMap(c => c.json_parse_failures || []).length, 0);
assert.deepEqual(generated.usage, { prompt_tokens: 710759, completion_tokens: 36791, total_tokens: 747550 });
assert.equal(generated.stages.tester.batch_count, 5);
assert.equal(generated.stages.challenger.batch_count, 4);
for (const stage of ['tester', 'challenger']) {
  assert(generated.stages[stage].required_check_ids.length > 0);
  assert.equal(generated.stages[stage].batch_operation_ids.length, generated.stages[stage].batch_count);
  for (const op of generated.stages[stage].batch_operation_ids) assert(generated.calls.some(c => c.operation_id === op));
}
for (const call of generated.calls) {
  assert(call.operation_id.startsWith(receipt.preparation_operation.operation_id + ':'));
  assert.equal(call.provider, 'deepseek'); assert.equal(call.requested_model, 'deepseek-flash'); assert.equal(call.actual_model, 'deepseek-flash');
}
assert.equal(receipt.assessment_answers, 0);
assert.equal(receipt.cycle.started_at, null);
assert(receipt.sessions.every(s => s.started_at === null));
assert.equal(receipt.assessment_situation.started_at, null);
for (const [name, value] of Object.entries(lifecycle.files)) {
  assert.equal(fileHash(path.join(here, 'run', name)), value.sha256, name);
  assert.equal(value.mode, '600');
}
assert.equal(lifecycle.state_absent, true);
for (const name of ['source-to-runtime-receipt.json', 'failure-receipt.json'])
  assert(lifecycle.files[name].mtime_ms < lifecycle.files['cleanup.json'].mtime_ms);
const provenance = read(path.join(here, 'run/source-provenance.json'));
assert.deepEqual(provenance.initial_counts, {users:1,organizations:0,memberships:0,profiles:0,cycles:0,assignments:0});
for (const [p, h] of Object.entries(provenance.source_files)) assert.equal(fileHash(path.join(root, p)), h, p);
assert.equal(objectHash(provenance.case.imported_json), provenance.case.imported_checksum);
const fixturePath = path.join(root, 'tests/browser/fixtures/path-start-release.json');
assert.equal(fileHash(fixturePath), provenance.release_receipt_sha256);
const fixture = read(fixturePath);
let qaCount = 0;
for (const c of fixture.cases) for (const qa of c.qa_evidence) {
  assert.equal(objectHash(qa.evidence_json), qa.evidence_checksum); qaCount++;
}
assert.equal(qaCount, 27);
const pkg = read(path.join(root, 'assessment_definitions/cases/competencies_4k/functional-personalization/0.5/case-package.json'));
for (const c of pkg.cases) {
  const frozen = structuredClone(c); frozen.status = 'FROZEN'; frozen.author_case.Status = 'FROZEN';
  assert.equal(objectHash(frozen), fixture.cases.find(x => x.case_id === c.case_id).content_checksum);
}
const methodology = read(path.join(root, 'assessment_definitions/methodologies/competencies_4k/1.1/methodology.json'));
const targets = methodology.competencies.flatMap(c => c.skills.flatMap(s => s.components.flatMap(x => x.indicators.map(i => i.id))));
const covered = new Set(pkg.cases.flatMap(c => c.indicator_targets.map(x => x.indicator_id)));
const missing = targets.filter(x => !covered.has(x)).sort();
assert.equal(targets.length, 61); assert.equal(covered.size, 39); assert.equal(missing.length, 22);
console.log(JSON.stringify({result:'PASS_OFFLINE_EVIDENCE_AUDIT',path_result:'FAIL_PLAN_NOT_READY',
  admission:'PASS',generation:1,tester_batches:5,challenger_batches:4,repair_used:false,
  unique_provider_operations:10,total_tokens:747550,candidate_to_saved_as:'LINKED',
  start:'NOT_RUN',presentation:'NOT_RUN',assessment_answers:0,owned_cleanup:'PASS',
  static_coverage:{full_target_count:61,catalog_target_count:39,missing_at_least:missing,
    note:'Source analysis, not reconstruction of deleted frozen plan or authorization to change coverage.'}},null,2));
