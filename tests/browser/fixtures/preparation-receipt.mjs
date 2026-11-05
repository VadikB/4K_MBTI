// Harness-only validation; admission is decided by the existing product, not here.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const required = (value, label) => assert.ok(value !== undefined && value !== null && value !== '', label);
const same = (left, right, label) => { required(left, label); required(right, label); assert.equal(left, right, label); };
const hash = (value) => assert.match(value ?? '', /^[a-f0-9]{64}$/, 'CHECKSUM_REQUIRED');

export function verifyPublishedProgram(receipt, selected) {
  const expected = selected?.program;
  required(expected, 'SELECTED_PUBLISHED_PROGRAM_REQUIRED');
  assert.equal(expected.status, 'published', 'SELECTED_PROGRAM_NOT_PUBLISHED');
  hash(expected.definition_checksum);
  for (const field of ['id', 'code', 'version', 'assignment_ref', 'status', 'definition_checksum',
    'assessment_configuration_id', 'catalog_version_id']) {
    same(receipt.program_definition?.[field], expected[field], 'SELECTED_PROGRAM_' + field.toUpperCase());
  }
}

export function verifyPreparation(receipt) {
  const generated = receipt.functional_generation;
  assert.equal(receipt.preparation_operation.status, 'completed', 'PREPARATION_NOT_COMPLETED');
  same(receipt.program_definition.catalog_version_id, receipt.catalog.id, 'PROGRAM_CATALOG_REF');
  same(receipt.assessment_configuration.catalog_version_id, receipt.catalog.id, 'CONFIG_CATALOG_REF');
  same(receipt.program_definition.assessment_configuration_id, receipt.assessment_configuration.id, 'PROGRAM_CONFIG_REF');
  same(receipt.program_definition.source_refs_json.prompt_bundle_checksum,
    receipt.assessment_configuration.prompt_bundle_checksum, 'PROMPT_REF');
  hash(receipt.assessment_configuration.prompt_bundle_checksum);
  if (Object.hasOwn(receipt, 'assignment_lineage')) {
    const lineage = receipt.assignment_lineage, cycle = receipt.cycle;
    assert.equal(lineage?.status, 'LINKED', 'ASSIGNMENT_LINEAGE_REQUIRED');
    same(lineage.assessment_configuration_id, receipt.assessment_configuration.id, 'LINEAGE_CONFIG_REF');
    same(lineage.assignment_id, cycle.assignment_id, 'CYCLE_ASSIGNMENT_REF');
    same(lineage.personalized_profile_id, cycle.personalized_profile_id, 'CYCLE_PROFILE_REF');
    same(String(lineage.personalized_profile_id), receipt.preparation_operation.requested_profile_id, 'OPERATION_PROFILE_REF');
    same(lineage.profile_checksum, receipt.preparation_operation.requested_profile_checksum, 'OPERATION_PROFILE_CHECKSUM');
    same(lineage.profile_checksum, cycle.profile_ref_json?.checksum, 'CYCLE_PROFILE_CHECKSUM');
    required(lineage.frozen_at, 'PROFILE_NOT_FROZEN');
    assert.equal(lineage.assigned_timing?.status, 'resolved', 'TIMING_NOT_RESOLVED');
    for (const [field, source] of [['time_budget_seconds', 'time_budget'], ['calendar_window_seconds', 'calendar_window']]) {
      assert.ok(Number.isInteger(cycle[field]) && cycle[field] > 0, 'INVALID_EFFECTIVE_TIME');
      same(cycle[field], lineage.assigned_timing[field], 'EFFECTIVE_TIME_REF');
      required(cycle.parameter_sources_json?.[source], 'TIME_SOURCE_MISSING');
      assert.deepEqual(cycle.parameter_sources_json[source], lineage.assigned_timing.sources[field], 'TIME_SOURCE_REF');
    }
    same(cycle.parameter_sources_json.resolution_checksum, lineage.assigned_timing.resolved_checksum, 'TIME_RESOLUTION_REF');
    assert.ok(['READY', 'LIMITED'].includes(receipt.plan?.status), 'PLAN_NOT_READY');
    required(receipt.plan?.revision_id, 'PLAN_REVISION_MISSING');
    hash(receipt.plan?.content_checksum);
    const admission = receipt.start_readiness;
    required(admission, 'SERVER_START_ADMISSION_REQUIRED');
    assert.equal(admission.contract, 'm7_start_readiness/1', 'START_CONTRACT');
    same(admission.cycle_id, cycle.cycle_id, 'START_CYCLE_REF');
    // Start readiness is a current-state decision, not a sticky PASS after start.
    if (!cycle.started_at) {
      assert.equal(admission.can_start, true, 'SERVER_START_NOT_ADMITTED');
      assert.deepEqual(admission.reasons, [], 'START_BLOCKERS_PRESENT');
      same(admission.plan_revision_id, receipt.plan.revision_id, 'START_PLAN_REVISION_REF');
      same(admission.plan_checksum, receipt.plan.content_checksum, 'START_PLAN_CHECKSUM_REF');
      same(admission.assessment_situation_id, receipt.assessment_situation.assessment_situation_id, 'START_AS_REF');
      same(admission.as_snapshot_checksum, receipt.assessment_situation.snapshot_checksum, 'START_AS_CHECKSUM_REF');
      same(admission.profile_checksum, lineage.profile_checksum, 'START_PROFILE_REF');
      same(admission.preparation_operation_id, receipt.preparation_operation.operation_id, 'START_OPERATION_REF');
      if (receipt.plan.status === 'LIMITED') {
        const saved = receipt.plan.diagnostics?.pilot_plan_binding;
        required(saved, 'APPROVED_PILOT_BINDING_REQUIRED');
        const pilot = admission.pilot_admission;
        required(pilot, 'EXACT_PILOT_ADMISSION_REQUIRED');
        hash(pilot.snapshot_checksum); hash(pilot.proposal_checksum); hash(pilot.binding_checksum);
        same(pilot.binding_checksum, saved.binding_checksum, 'PILOT_BINDING_REF');
        same(pilot.snapshot_checksum, saved.admission_snapshot?.snapshot_checksum, 'PILOT_SNAPSHOT_REF');
        same(pilot.proposal_checksum, saved.admission_snapshot?.review?.proposal_payload_checksum, 'PILOT_PROPOSAL_REF');
        same(pilot.human_decision_id, saved.admission_snapshot?.owner_decision?.decision_id, 'PILOT_DECISION_REF');
        same(pilot.program_ref?.checksum, receipt.program_definition.definition_checksum, 'PILOT_PROGRAM_REF');
        assert.deepEqual(pilot.program_ref, saved.program_ref, 'PILOT_PROGRAM_BINDING_REF');
        assert.deepEqual(receipt.plan.diagnostics?.uncovered_planned_target_ids, [], 'PILOT_PLANNED_GAP');
      }
    }
  }
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

export function verifyFirstCase(receipt, before, selected) {
  if (selected !== undefined) {
    verifyPublishedProgram(before, selected);
    verifyPublishedProgram(receipt, selected);
  }
  verifyPreparation(before);
  verifyPreparation(receipt);
  if (Object.hasOwn(before, 'assignment_lineage')) {
    same(receipt.plan?.revision_id, before.plan?.revision_id, 'PRE_START_PLAN_CHANGED');
    same(receipt.plan?.content_checksum, before.plan?.content_checksum, 'PRE_START_PLAN_CHANGED');
    assert.deepEqual(receipt.plan?.diagnostics?.pilot_plan_binding,
      before.plan?.diagnostics?.pilot_plan_binding, 'PRE_START_PILOT_BINDING_CHANGED');
  }
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
      JSON.parse(fs.readFileSync(process.argv[3], 'utf8')),
      process.argv[4] ? JSON.parse(fs.readFileSync(process.argv[4], 'utf8')) : undefined);
  } catch {
    // No arbitrary receipt values, assertions, credentials or prompts in summary output.
    process.stderr.write('FIRST_CASE_EVIDENCE_INVALID\n');
    process.exitCode = 1;
  }
}
