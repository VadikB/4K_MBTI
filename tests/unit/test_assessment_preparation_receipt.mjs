import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { verifyPreparation, verifyFirstCase } from '../browser/fixtures/preparation-receipt.mjs';

const fixture = () => JSON.parse(fs.readFileSync(new URL('../browser/fixtures/first-case-success.json', import.meta.url)));
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
