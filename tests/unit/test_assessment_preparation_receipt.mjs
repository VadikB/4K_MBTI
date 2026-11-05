import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { verifyPreparation, verifyFirstCase, verifyPublishedProgram } from '../browser/fixtures/preparation-receipt.mjs';

function selectedFixture(version = 'synthetic-next-version') {
  const receipt = fixture();
  Object.assign(receipt.program_definition, { code: 'specialist_pilot', version,
    assignment_ref: 'specialist-pilot', status: 'published', definition_checksum: 'a'.repeat(64) });
  return { receipt, selected: { program: structuredClone(receipt.program_definition) } };
}
for (const version of ['1.1', 'synthetic-next-version']) test(`exact selected program ${version}`, () => {
  const { receipt, selected } = selectedFixture(version);
  assert.doesNotThrow(() => verifyFirstCase(receipt, before(receipt), selected));
});
for (const field of ['id', 'code', 'version', 'assignment_ref', 'status', 'definition_checksum',
  'assessment_configuration_id', 'catalog_version_id']) {
  for (const phase of ['before', 'after']) test(`selected ${field} drift ${phase} blocks success`, () => {
    const { receipt, selected } = selectedFixture();
    const initial = before(receipt);
    (phase === 'before' ? initial : receipt).program_definition[field] = 'different';
    assert.throws(() => verifyFirstCase(receipt, initial, selected), /SELECTED_PROGRAM_/);
  });
}
test('missing selected source is rejected, not inferred from actual program', () => {
  assert.throws(() => verifyPublishedProgram(fixture(), {}), /SELECTED_PUBLISHED_PROGRAM_REQUIRED/);
});

function fixture() {
  return JSON.parse(fs.readFileSync(new URL('../browser/fixtures/first-case-success.json', import.meta.url)));
}
function before(receipt) {
  const value = structuredClone(receipt);
  value.cycle.started_at = value.sessions[0].started_at = value.assessment_situation.started_at = null;
  return value;
}
for (const status of ['PASS', 'PASS_WITH_WARNINGS']) {
  for (const repair of [false, true]) test(`${status}, final repair=${repair}`, () => {
    const value = fixture(), generated = value.functional_generation;
    generated.admission_status = status;
    if (repair) {
      generated.repair_used = true;
      generated.final_generation_operation_id = generated.repair_operation_id = 'synthetic-prepare:repair';
      generated.stages.generation.operation_id = generated.repair_operation_id;
      generated.calls.push({ ...generated.calls[0], operation_id: generated.repair_operation_id, kind: 'generation_repair' });
    }
    assert.doesNotThrow(() => verifyFirstCase(value, before(value)));
  });
}
for (const status of ['INCOMPLETE', 'FAIL', 'REVIEW_REQUIRED', null]) test(`reject admission ${status}`, () => {
  const value = fixture(); value.functional_generation.admission_status = status;
  assert.throws(() => verifyPreparation(value), /AS_NOT_ADMITTED/);
});
const corruptions = {
  unadmitted: r => { r.functional_generation.admitted_for_participant = false; },
  'missing generation': r => { r.functional_generation.calls.shift(); },
  'missing tester': r => { r.functional_generation.stages.tester.batch_count = 0; },
  'missing challenger': r => { r.functional_generation.stages.challenger.required_check_ids = []; },
  'missing batch': r => { r.functional_generation.stages.tester.batch_operation_ids = []; },
  'foreign operation': r => { r.functional_generation.calls[1].operation_id = 'foreign:tester'; },
  'wrong final candidate': r => { r.functional_generation.candidate_recomputed_checksum = '2'.repeat(64); },
  'wrong final generation': r => { r.functional_generation.final_generation_operation_id = 'missing'; },
  'wrong repair ref': r => { r.functional_generation.repair_used = true; },
  'wrong compiled ref': r => { r.saved_checksums.case_ref.checksum = '3'.repeat(64); },
  'wrong snapshot': r => { r.saved_checksums.snapshot_recomputed = '4'.repeat(64); },
  'wrong execution ref': r => { r.saved_checksums.execution_payload_recomputed = '5'.repeat(64); },
  'missing checksums': r => { delete r.saved_checksums.snapshot_recomputed; delete r.assessment_situation.snapshot_checksum; },
  'wrong presented AS': r => { r.presented_as.assessment_situation_id = 'different-as'; },
  'wrong presented payload': r => { r.presented_as.participant_payload_checksum = '6'.repeat(64); },
  'not started': r => { r.cycle.started_at = null; },
  'assessment answer': r => { r.assessment_answers = 1; },
};
for (const [name, corrupt] of Object.entries(corruptions)) test(`warnings do not bypass ${name}`, () => {
  const value = fixture(); value.functional_generation.admission_status = 'PASS_WITH_WARNINGS';
  const initial = before(value); corrupt(value);
  assert.throws(() => verifyFirstCase(value, initial));
});
test('pre-start chain cannot change after start', () => {
  const value = fixture(), initial = before(value);
  initial.assessment_situation.assessment_situation_id = 'different-as';
  assert.throws(() => verifyFirstCase(value, initial), /PRE_START_CHAIN_CHANGED/);
});

function linkedFixture() {
  const r = fixture(), checksum = '7'.repeat(64);
  r.preparation_operation.requested_profile_id = '101';
  r.preparation_operation.requested_profile_checksum = checksum;
  r.assignment_lineage = { status: 'LINKED', assignment_id: 41, personalized_profile_id: 101,
    assessment_configuration_id: 2, profile_checksum: checksum, frozen_at: '2026-11-04T00:00:00Z',
    assigned_timing: { status: 'resolved', time_budget_seconds: 3600, calendar_window_seconds: 259200,
      sources: { time_budget_seconds: { source: 'synthetic-default' }, calendar_window_seconds: { source: 'synthetic-default' } },
      resolved_checksum: '8'.repeat(64) } };
  Object.assign(r.cycle, { assignment_id: 41, personalized_profile_id: 101, profile_ref_json: { checksum },
    time_budget_seconds: 3600, calendar_window_seconds: 259200,
    parameter_sources_json: { time_budget: { source: 'synthetic-default' }, calendar_window: { source: 'synthetic-default' },
      resolution_checksum: '8'.repeat(64) } });
  r.plan = { status: 'READY', revision_id: 'synthetic-revision', content_checksum: '9'.repeat(64) };
  r.start_readiness = { contract: 'm7_start_readiness/1', can_start: true, reasons: [],
    cycle_id: r.cycle.cycle_id, plan_revision_id: r.plan.revision_id, plan_checksum: r.plan.content_checksum,
    assessment_situation_id: r.assessment_situation.assessment_situation_id,
    as_snapshot_checksum: r.assessment_situation.snapshot_checksum, profile_checksum: checksum,
    preparation_operation_id: r.preparation_operation.operation_id };
  return r;
}
test('PATH linked profile/assignment/plan/timing retains PASS_WITH_WARNINGS', () => {
  const r = linkedFixture(); r.functional_generation.admission_status = 'PASS_WITH_WARNINGS';
  assert.doesNotThrow(() => verifyFirstCase(r, before(r)));
});
for (const [name, corrupt] of Object.entries({
  'unknown lineage': r => { r.assignment_lineage.status = 'UNKNOWN_OR_AMBIGUOUS'; },
  'foreign assignment': r => { r.cycle.assignment_id = 99; },
  'foreign profile': r => { r.cycle.personalized_profile_id = 99; },
  'wrong operation profile': r => { r.preparation_operation.requested_profile_id = '99'; },
  'wrong profile checksum': r => { r.cycle.profile_ref_json.checksum = '0'.repeat(64); },
  'unfrozen profile': r => { r.assignment_lineage.frozen_at = null; },
  'missing time source': r => { delete r.cycle.parameter_sources_json.time_budget; },
  'invalid time': r => { r.cycle.calendar_window_seconds = 0; },
  'wrong time source': r => { r.cycle.parameter_sources_json.time_budget = { source: 'foreign' }; },
  'missing plan revision': r => { delete r.plan.revision_id; },
})) test(`PATH rejects ${name}`, () => {
  const r = linkedFixture(); corrupt(r);
  assert.throws(() => verifyFirstCase(r, before(r)));
});

for (const [name, corrupt] of Object.entries({
  'missing server decision': r => { delete r.start_readiness; },
  'server denied': r => { r.start_readiness.can_start = false; },
  'foreign server cycle': r => { r.start_readiness.cycle_id = 'other'; },
  'stale server revision': r => { r.start_readiness.plan_revision_id = 'old'; },
  'wrong server hash': r => { r.start_readiness.plan_checksum = '0'.repeat(64); },
  'foreign server AS': r => { r.start_readiness.assessment_situation_id = 'other'; },
  'blockers despite true': r => { r.start_readiness.reasons.push('BLOCKED'); },
  'LIMITED without exact admission': r => { r.plan.status = 'LIMITED'; },
})) test(`pre-start rejects ${name}`, () => {
  const r = before(linkedFixture()); corrupt(r);
  assert.throws(() => verifyPreparation(r));
});

test('exact LIMITED admission retains stages and final AS checks', () => {
  const r = before(linkedFixture());
  r.plan.status = 'LIMITED';
  const pilot = { snapshot_checksum: 'a'.repeat(64), proposal_checksum: 'b'.repeat(64),
    binding_checksum: 'c'.repeat(64), human_decision_id: 'synthetic-PM',
    program_ref: { checksum: 'd'.repeat(64) } };
  r.program_definition.definition_checksum = pilot.program_ref.checksum;
  r.start_readiness.pilot_admission = pilot;
  r.plan.diagnostics = { uncovered_planned_target_ids: [], pilot_plan_binding: {
    binding_checksum: pilot.binding_checksum, program_ref: pilot.program_ref,
    admission_snapshot: { snapshot_checksum: pilot.snapshot_checksum,
      review: { proposal_payload_checksum: pilot.proposal_checksum }, owner_decision: { decision_id: pilot.human_decision_id } },
  } };
  assert.doesNotThrow(() => verifyPreparation(r));
  r.functional_generation.admitted_for_participant = false;
  assert.throws(() => verifyPreparation(r), /AS_NOT_ADMITTED/);
});
