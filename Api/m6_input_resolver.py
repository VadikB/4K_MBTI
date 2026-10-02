"""Адаптер сохранённого C-45. Не исполняет сценарий и не меняет состояние AS."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import UUID

from Api.assessment_configuration import definition_checksum
from Api.assessment_case_contracts import AssessmentSituationV2
from Api.m5_case_runtime import checksum

M2 = Path(__file__).resolve().parents[1] / 'assessment_definitions/methodologies/competencies_4k/1.1'
SOURCES = Path(__file__).resolve().parents[1] / 'docs/methodology/source-sets/2026-10-01/manifest.json'


def load_criteria(snapshot: dict, directory: Path = M2) -> list[dict]:
    data = (directory / 'methodology.json').read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    if digest != manifest['artifact']['sha256'] or not any(x['checksum'] == digest for x in snapshot['methodology_refs']):
        raise ValueError('CHECKSUM_MISMATCH')
    sources = json.loads(SOURCES.read_bytes())['entries']
    criteria = {}
    for competency in json.loads(data)['competencies']:
        source = next(x for x in sources if x['id'] == f"M2.{competency['id']}.matrix")
        if not any(x['sha256'] == source['sha256'] for x in manifest['sources']):
            raise ValueError('SOURCE_UNRESOLVED')
        for skill in competency['skills']:
            for component in skill['components']:
                for indicator in component['indicators']:
                    criteria[indicator['id']] = {**indicator, 'skill_id': skill['id'], 'component_id': component['id'],
                        'm2_version': 'v' + source['version'], 'source_ref': source, 'package_sha256': digest}
    result = []
    for target in snapshot['indicator_targets']:
        criterion = criteria.get(target['indicator_id'])
        if not criterion or any(criterion[k] != target[k] for k in ('m2_version', 'component_id', 'skill_id')):
            raise ValueError('TARGET_SET_MISMATCH')
        if not all(criterion.get(k) for k in ('function', 'product', 'evidence_pattern', 'boundary')) or set(criterion['levels']) != {'L0','L1','L2','L3'}:
            raise ValueError('SOURCE_UNRESOLVED')
        result.append(criterion)
    return result


def normalize(handoff: dict, row: dict, cycle: dict, session: dict, criteria: list[dict]) -> dict:
    envelope = handoff['envelope_json']
    snapshot = row['snapshot_json']
    execution = row['execution_payload_json']
    AssessmentSituationV2.model_validate(snapshot)
    if envelope.get('schema_version') != 1 or envelope.get('contract') != 'C-45':
        raise ValueError('M6_SCHEMA_UNSUPPORTED')
    if checksum(envelope) != handoff['envelope_checksum'] or checksum(snapshot) != row['snapshot_checksum'] or checksum(execution) != snapshot['execution_payload_ref']['checksum']:
        raise ValueError('CHECKSUM_MISMATCH')
    if row['usage_scope'] != 'qa':
        raise ValueError('M6_QA_ONLY')
    as_id = str(row['assessment_situation_id'])
    if str(handoff['assessment_situation_db_id']) != str(row['id']) or envelope['assessment_situation_ref'] != {'id': as_id, 'checksum': row['snapshot_checksum']}:
        raise ValueError('M6_OWNER_MISMATCH')
    if snapshot['assessment_situation_id'] != as_id or int(snapshot['cycle_ref']['id']) != cycle['id'] or int(snapshot['session_ref']['id']) != session['id']:
        raise ValueError('M6_OWNER_MISMATCH')
    if (row['cycle_db_id'], row['session_db_id'], session['cycle_db_id']) != (cycle['id'], session['id'], cycle['id']):
        raise ValueError('M6_OWNER_MISMATCH')
    if snapshot['cycle_ref']['checksum'] != checksum({'cycle_id': str(cycle['cycle_id']), 'target_set_checksum': cycle['target_set_checksum']}):
        raise ValueError('CHECKSUM_MISMATCH')
    if snapshot['session_ref']['checksum'] != checksum({'session_id': str(session['session_id']), 'cycle_id': str(cycle['cycle_id']), 'ordinal': session['ordinal']}):
        raise ValueError('CHECKSUM_MISMATCH')
    for key in ('cycle_ref','session_ref','case_ref','profile_ref','methodology_refs','indicator_targets','execution_payload_ref'):
        if envelope[key] != snapshot[key]:
            raise ValueError('M6_COMPOSITION_MISMATCH')
    mode = handoff['mode']
    if mode not in ('interim','final') or envelope['mode'] != mode:
        raise ValueError('M6_MODE_INVALID')
    if envelope['assessment_situation_status'] != ('closed' if mode == 'final' else 'scenario_ended') or (mode == 'final' and row['status'] != 'closed'):
        raise ValueError('M6_STATE_INVALID')
    turns, events = envelope['dialogue']['turns'], envelope['dialogue']['events']
    sequence = [x['sequence_no'] for x in turns + events]
    boundary = handoff['boundary_sequence']
    if len(set(sequence)) != len(sequence) or any(x <= 0 or x > boundary for x in sequence) or max(sequence,default=0) != boundary or envelope['boundary_sequence'] != boundary:
        raise ValueError('M6_BOUNDARY_INVALID')
    if len({x['turn_id'] for x in turns}) != len(turns) or len({x['event_id'] for x in events}) != len(events):
        raise ValueError('M6_DUPLICATE_ID')
    if envelope['boundary'] != {'inclusive_sequence': boundary, 'turn_ids': [x['turn_id'] for x in turns], 'event_ids': [x['event_id'] for x in events]}:
        raise ValueError('M6_BOUNDARY_INVALID')
    if not any(x['event_type'] == 'scenario_started' for x in events):
        raise ValueError('SOURCE_UNRESOLVED')
    closing = 'assessment_situation_closed' if mode == 'final' else 'scenario_completed'
    if not any(x['event_type'] == closing for x in events):
        raise ValueError('M6_STATE_INVALID')
    targets = snapshot['indicator_targets']
    if {x['id'] for x in criteria} != {x['indicator_id'] for x in targets} or len(criteria) != len(targets):
        raise ValueError('TARGET_SET_MISMATCH')
    materials = []
    for presented in envelope['presented_materials']:
        event = next((x for x in events if x['event_id'] == presented['event_id']), None)
        material = next((x for x in execution['materials'] if x['material_id'] == presented['material_id']), None)
        if not event or not material or event['material_id'] != material['material_id'] or event['sequence_no'] != presented['sequence_no']:
            raise ValueError('SOURCE_UNRESOLVED')
        materials.append({'material_id': material['material_id'], 'available_sequence': event['sequence_no'],
                          'content': material.get('participant_payload'), 'event_id': event['event_id']})
    # raw profile, internal DB IDs and contact fields are deliberately excluded.
    payload = {'as_id': as_id, 'cycle_id': str(cycle['cycle_id']), 'session_id': str(session['session_id']),
        'dialogue_id': f'as:{as_id}:dialogue:1', 'mode': 'final_as' if mode == 'final' else 'interim',
        'indicator_targets': deepcopy(targets), 'criteria': criteria,
        'turns': deepcopy(turns), 'events': deepcopy(events), 'materials': materials,
        'initial_presentation': deepcopy(snapshot['participant_payload']),
        'context': {'base_role': snapshot['base_role']}, 'usage_scope': 'qa',
        'as_snapshot_ref': envelope['assessment_situation_ref'], 'execution_payload_ref': snapshot['execution_payload_ref'],
        'handoff_ref': {'id': str(handoff['handoff_id']), 'checksum': handoff['envelope_checksum'], 'checksum_kind': 'm5_canonical_json_lf_v1'},
        'last_included_turn_id': max(turns,key=lambda x:x['sequence_no'])['turn_id'] if turns else None}
    payload['material_revision'] = {'boundary_sequence': boundary, 'material_sha256': definition_checksum(payload), 'checksum_kind':'definition_json_v1'}
    return payload


def resolve(connection, handoff_id: str) -> tuple[int, dict]:
    h = connection.execute('SELECT * FROM m5_c45_handoffs WHERE handoff_id=%s', (UUID(handoff_id),)).fetchone()
    if not h:
        raise ValueError('M6_HANDOFF_NOT_FOUND')
    row = connection.execute('SELECT * FROM m5_assessment_situations WHERE id=%s', (h['assessment_situation_db_id'],)).fetchone()
    cycle = connection.execute('SELECT * FROM m5_cycles WHERE id=%s', (row['cycle_db_id'],)).fetchone()
    session = connection.execute('SELECT * FROM m5_cycle_sessions WHERE id=%s', (row['session_db_id'],)).fetchone()
    if not cycle or not session:
        raise ValueError('M6_OWNER_MISMATCH')
    return row['id'], normalize(dict(h),dict(row),dict(cycle),dict(session),load_criteria(row['snapshot_json']))
