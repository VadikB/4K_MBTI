// Harness-only validation; admission is decided by the existing product, not here.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const required = (value, label) => assert.ok(value !== undefined && value !== null && value !== '', label);
const same = (left, right, label) => { required(left, label); required(right, label); assert.equal(left, right, label); };
const hash = (value) => assert.match(value ?? '', /^[a-f0-9]{64}$/, 'CHECKSUM_REQUIRED');

export function verifyPreparation(receipt) {
  const generated = receipt.functional_generation;
  assert.equal(receipt.preparation_operation.status, 'completed', 'PREPARATION_NOT_COMPLETED');
  same(receipt.program_definition.catalog_version_id, receipt.catalog.id, 'PROGRAM_CATALOG_REF');
  same(receipt.assessment_configuration.catalog_version_id, receipt.catalog.id, 'CONFIG_CATALOG_REF');
  same(receipt.program_definition.assessment_configuration_id, receipt.assessment_configuration.id, 'PROGRAM_CONFIG_REF');
  same(receipt.program_definition.source_refs_json.prompt_bundle_checksum,
    receipt.assessment_configuration.prompt_bundle_checksum, 'PROMPT_REF');
  hash(receipt.assessment_configuration.prompt_bundle_checksum);
  same(receipt.cycle.catalog_ref_json.checksum, receipt.catalog.manifest_checksum, 'CATALOG_CHECKSUM');
  hash(receipt.catalog.manifest_checksum);
  assert.equal(generated.present, true, 'GENERATION_MISSING');
  assert.ok(['PASS', 'PASS_WITH_WARNINGS'].includes(generated.admission_status), 'AS_NOT_ADMITTED');
  assert.equal(generated.admitted_for_participant, true, 'AS_NOT_ADMITTED');
  hash(generated.candidate_checksum);
  same(generated.candidate_checksum, generated.candidate_recomputed_checksum, 'CANDIDATE_CHECKSUM');
  same(generated.candidate_ref.checksum, generated.candidate_checksum, 'CANDIDATE_REF');
  same(generated.candidate_ref.case_id, receipt.saved_checksums.case_ref.id, 'CASE_ID_REF');
  same(generated.candidate_ref.case_version, receipt.saved_checksums.case_ref.version, 'CASE_VERSION_REF');
  hash(generated.compiled_case_checksum);
  same(generated.compiled_case_checksum, receipt.saved_checksums.case_ref.checksum, 'COMPILED_CASE_REF');
  hash(receipt.assessment_situation.snapshot_checksum);
  same(receipt.assessment_situation.snapshot_checksum, receipt.saved_checksums.snapshot_recomputed, 'SNAPSHOT_CHECKSUM');
  hash(receipt.saved_checksums.execution_payload_ref.checksum);
  same(receipt.saved_checksums.execution_payload_ref.checksum,
    receipt.saved_checksums.execution_payload_recomputed, 'EXECUTION_PAYLOAD_REF');
  const calls = generated.calls;
  assert.ok(calls.some((call) => call.kind === 'generation'), 'GENERATION_STAGE_MISSING');
  assert.equal(new Set(calls.map((call) => call.operation_id)).size, calls.length, 'DUPLICATE_OPERATION');
  const generation = calls.find((call) => call.operation_id === generated.final_generation_operation_id);
  assert.ok(generation, 'FINAL_GENERATION_MISSING');
  assert.equal(generation.kind, generated.repair_used ? 'generation_repair' : 'generation', 'FINAL_GENERATION_KIND');
  if (generated.repair_used) same(generated.final_generation_operation_id, generated.repair_operation_id, 'REPAIR_REF');
  same(generated.stages.generation.operation_id, generated.final_generation_operation_id, 'FINAL_STAGE_REF');
  for (const stage of ['tester', 'challenger']) {
    const value = generated.stages[stage];
    assert.ok(value.batch_count > 0, 'REQUIRED_STAGE_MISSING');
    assert.ok(value.required_check_ids.length > 0, 'REQUIRED_CHECKS_MISSING');
    assert.equal(value.batch_operation_ids.length, value.batch_count, 'BATCH_COUNT_MISMATCH');
    assert.equal(new Set(value.batch_operation_ids).size, value.batch_count, 'DUPLICATE_BATCH');
    for (const id of value.batch_operation_ids) {
      assert.ok(calls.some((call) => call.operation_id === id), 'BATCH_OPERATION_MISSING');
    }
  }
  for (const call of calls) {
    required(receipt.preparation_operation.operation_id, 'PREPARATION_ID_REQUIRED');
    assert.ok(call.operation_id.startsWith(receipt.preparation_operation.operation_id + ':'), 'OPERATION_OWNER_REF');
    assert.equal(call.provider, 'deepseek', 'PROVIDER');
    assert.equal(call.requested_model, 'deepseek-flash', 'REQUESTED_MODEL');
    assert.equal(call.actual_model, 'deepseek-flash', 'ACTUAL_MODEL');
  }
}

export function verifyFirstCase(receipt, before) {
  verifyPreparation(before);
  verifyPreparation(receipt);
  assert.equal(receipt.http_start_status, 201, 'START_HTTP_STATUS');
  assert.equal(receipt.assessment_answers, 0, 'ASSESSMENT_ANSWERS_NOT_ZERO');
  assert.deepEqual(receipt.participant_state, { profiles: 1, cycles: 1, started: 1, operations: 1 }, 'PARTICIPANT_STATE');
  required(receipt.cycle.started_at, 'CYCLE_NOT_STARTED');
  required(receipt.sessions[0].started_at, 'SESSION_NOT_STARTED');
  required(receipt.assessment_situation.started_at, 'AS_NOT_STARTED');
  assert.equal(before.assessment_answers, 0, 'PRE_START_ANSWERS');
  assert.equal(before.cycle.started_at, null, 'CYCLE_ALREADY_STARTED');
  assert.equal(before.sessions[0].started_at, null, 'SESSION_ALREADY_STARTED');
  assert.equal(before.assessment_situation.started_at, null, 'AS_ALREADY_STARTED');
  for (const [afterValue, beforeValue] of [
    [receipt.preparation_operation.operation_id, before.preparation_operation.operation_id],
    [receipt.cycle.cycle_id, before.cycle.cycle_id],
    [receipt.sessions[0].session_id, before.sessions[0].session_id],
    [receipt.assessment_situation.assessment_situation_id, before.assessment_situation.assessment_situation_id],
    [receipt.functional_generation.candidate_checksum, before.functional_generation.candidate_checksum],
    [receipt.assessment_situation.snapshot_checksum, before.assessment_situation.snapshot_checksum],
  ]) same(afterValue, beforeValue, 'PRE_START_CHAIN_CHANGED');
  same(receipt.presented_as.assessment_situation_id, receipt.assessment_situation.assessment_situation_id, 'PRESENTED_AS_REF');
  hash(receipt.saved_checksums.participant_payload);
  same(receipt.presented_as.participant_payload_checksum, receipt.saved_checksums.participant_payload, 'PRESENTED_PAYLOAD_REF');
  assert.equal(receipt.presented_as.dom_introduction_matched, true, 'DOM_NOT_MATCHED');
  assert.equal(receipt.presented_as.screenshot, 'first-case.png', 'SCREENSHOT_REF');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    verifyFirstCase(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')),
      JSON.parse(fs.readFileSync(process.argv[3], 'utf8')));
  } catch {
    // No arbitrary receipt values, assertions, credentials or prompts in summary output.
    process.stderr.write('FIRST_CASE_EVIDENCE_INVALID\n');
    process.exitCode = 1;
  }
}
