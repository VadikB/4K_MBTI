"""Source-backed presentation fixtures only; no provider/DB/pilot admission."""
from copy import deepcopy
import json
from pathlib import Path
import sys

from Api.m5_case_runtime import build_assessment_situation

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'assessment_definitions/cases/competencies_4k/functional-personalization/0.5'
LEGACY_FIELDS = ('initial_situation', 'trigger', 'assessee_position',
                 'participants_and_positions', 'assessee_task', 'conditions_and_constraints')


def case_value(case_id):
    return deepcopy(next(case for case in json.loads((PACKAGE / 'case-package.json').read_text())['cases']
                         if case['case_id'] == case_id))


def sample(case_id='CASE.SPEC.02', *, functional=True, case=None, schema_profile=None, policy=None):
    case = deepcopy(case) if case is not None else case_value(case_id)
    ref = {'id': 'synthetic-projection', 'version': '1', 'checksum': 'a' * 64}
    compiler = json.loads((PACKAGE / 'manifest.json').read_text())['compiler']
    if schema_profile is not None:
        compiler['source_schema_profile'] = schema_profile
    operations = {'functional_personalization': {'source_snapshot': {'refs': {
        'package': {'compiler': compiler}}}}} if functional else {}
    snapshot, execution = build_assessment_situation(
        assessment_situation_id='AS.PROJECTION.SYNTHETIC.' + case_id.rsplit('.', 1)[-1],
        cycle_ref=ref, session_ref=ref, case_value=case, profile_ref=ref,
        profile_snapshot={'base_role': case['base_role']}, methodology_refs=[ref],
        substitutions=[], qa_evidence=[], ai_operations=operations,
        policy=policy if policy is not None else {
            'allowed_case_statuses': ['WORKING'], 'required_evidence_scopes': []},
    )
    return {'scope': 'SYNTHETIC_COMPONENT_PRESENTATION_NOT_PILOT_ADMISSION',
            'source_case': case, 'snapshot': snapshot, 'execution': execution}


if __name__ == '__main__':
    # stdout only, consumed by the browser component fixture; no private data.
    value = sample(sys.argv[1] if len(sys.argv) > 1 else 'CASE.SPEC.02')
    print(json.dumps({'scope': value['scope'], 'participant_payload': value['snapshot']['participant_payload']},
                     ensure_ascii=False))
