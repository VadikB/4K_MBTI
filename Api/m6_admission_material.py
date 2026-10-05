"""Сохранённая цепочка допуска PM-05; только адресованные итоговые revisions."""
from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from Api.assessment_configuration import definition_checksum
from Api.m5_case_runtime import checksum
from Api.m6_contracts import validate_analysis
from Api.m6_assessment_contracts import validate_assessment


def _verified(value, digest):
    if definition_checksum(value) != digest and checksum(value) != digest:
        raise ValueError('RECOMMENDATION_SOURCE_CHECKSUM')


def resolve(connection, *, cycle_id: str, observations: list[dict]) -> list[dict]:
    ids = [x['revision_id'] for x in observations]
    if len(ids) != len(set(ids)):
        raise ValueError('M6_ADMISSION_AMBIGUOUS_IA')
    projections = []
    for observation in observations:
        # No-assessment entries are explicitly not IA; keep them as rejected candidates.
        if observation['revision_id'].startswith('non-numeric:'):
            continue
        row = connection.execute('''SELECT ir.content_json,ir.content_hash,ia.indicator_id,
            ar.id AS assessment_id,ar.output_json,ar.output_hash,q.input_json,q.input_hash,
            q.evidence_revision_id,er.output_json AS evidence_json,er.output_hash AS evidence_hash,
            eq.input_json AS material_json,eq.input_hash AS material_hash,
            s.assessment_situation_id,s.usage_scope,s.snapshot_json,s.snapshot_checksum,c.cycle_id
            FROM m6_indicator_assessment_revisions ir
            JOIN m6_indicator_assessments ia ON ia.id=ir.indicator_assessment_id
            JOIN m6_assessment_revisions ar ON ar.id=ir.assessment_revision_id
            JOIN m6_assessment_requests q ON q.id=ar.request_id
            JOIN m6_analysis_revisions er ON er.id=q.evidence_revision_id
            JOIN m6_processing_requests eq ON eq.id=er.request_id
            JOIN m5_assessment_situations s ON s.id=ir.as_db_id
            JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE ir.id=%s
            AND ia.as_db_id=ir.as_db_id AND ar.as_db_id=ir.as_db_id
            AND q.as_db_id=ir.as_db_id AND er.as_db_id=ir.as_db_id AND eq.as_db_id=ir.as_db_id''',
            (UUID(observation['revision_id']),)).fetchone()
        if not row:
            raise ValueError('M6_ADMISSION_IA_UNRESOLVED')
        for value, digest in (('content_json','content_hash'),('output_json','output_hash'),
                              ('input_json','input_hash'),('evidence_json','evidence_hash'),('material_json','material_hash')):
            _verified(row[value], row[digest])
        for field, source in (('assessment_revision_id','assessment_id'),('evidence_revision_id','evidence_revision_id'),
                              ('assessment_situation_id','assessment_situation_id'),('indicator_id','indicator_id')):
            if observation[field] != str(row[source]):
                raise ValueError('M6_ADMISSION_REFERENCE_MISMATCH')
        if str(row['cycle_id']) != cycle_id:
            raise ValueError('M6_ADMISSION_CYCLE_MISMATCH')
        material, analysis, target = row['material_json'], row['evidence_json'], row['content_json']
        if checksum(row['snapshot_json']) != row['snapshot_checksum']:
            raise ValueError('M6_ADMISSION_SNAPSHOT_CHECKSUM')
        from Api.m6_input_resolver import load_criteria
        if row['material_json']['criteria'] != load_criteria(row['snapshot_json']):
            raise ValueError('M6_ADMISSION_M2_UNVERIFIED')
        if row['usage_scope'] == 'assessment':
            from Api.m10_input_resolver import resolve as resolve_handoff
        else:
            from Api.m6_input_resolver import resolve as resolve_handoff
        _, original_material = resolve_handoff(connection, material['handoff_ref']['id'])
        if original_material != material:
            raise ValueError('M6_ADMISSION_MATERIAL_SNAPSHOT_MISMATCH')
        if row['input_json']['mode'] != 'final' or material['mode'] != 'final_as':
            raise ValueError('M6_ADMISSION_FINAL_REQUIRED')

        if material['cycle_id'] != cycle_id or material['as_id'] != observation['assessment_situation_id']:
            raise ValueError('M6_ADMISSION_MATERIAL_SCOPE')
        if row['input_json']['material'] != material or row['input_json']['evidence_analysis'] != analysis:
            raise ValueError('M6_ADMISSION_SOURCE_MISMATCH')
        validate_analysis(analysis, material)
        validate_assessment(row['output_json'], row['input_json'])
        matches = [x for x in row['output_json']['targets'] if x['indicator_id'] == observation['indicator_id']]
        if matches != [target]:
            raise ValueError('M6_ADMISSION_AMBIGUOUS_TARGET')
        for key in ('indicator_id','m2_version','status','outcome','opportunity','refs','confidence','contradictions'):
            if observation.get(key) != target.get(key):
                raise ValueError('M6_ADMISSION_OBSERVATION_MISMATCH')
        criterion = [x for x in material['criteria'] if x['id'] == target['indicator_id']]
        if len(criterion) != 1:
            raise ValueError('M6_ADMISSION_CRITERION_UNRESOLVED')
        bundles = [x for x in analysis['bundles'] if x['indicator_id'] == target['indicator_id']]
        if len(bundles) != 1:
            raise ValueError('M6_ADMISSION_BUNDLE_UNRESOLVED')
        bundle = bundles[0]
        # Resolve every reference through the accepted M6 snapshot down to material.
        traces = []
        for ref in target['refs']:
            if ref['kind'] in ('evidence','bundle'):
                if ref['kind'] == 'bundle' and ref['id'] != target['indicator_id']:
                    raise ValueError('M6_ADMISSION_CROSS_TARGET_BUNDLE')
                evidence_ids = [ref['id']] if ref['kind'] == 'evidence' else bundle['evidence_ids']
                for eid in evidence_ids:
                    evidence = next(x for x in analysis['evidence'] if x['id'] == eid)
                    fragments = [x for x in analysis['fragments'] if x['id'] in evidence['fragment_ids']]
                    traces.append({'ref': deepcopy(ref), 'evidence_id': eid,
                        'interpretation': evidence['interpretation'], 'limitations': evidence['limitations'],
                        'fragments': deepcopy(fragments)})
            else:
                plural, id_key = {'turn':('turns','turn_id'), 'event':('events','event_id'),
                                  'material':('materials','material_id')}[ref['kind']]
                entries = [x for x in material[plural] if x[id_key] == ref['id']]
                if len(entries) != 1:
                    raise ValueError('M6_ADMISSION_MATERIAL_UNRESOLVED')
                traces.append({'ref':deepcopy(ref), 'material':deepcopy(entries[0])})
        projections.append({'revision_id':observation['revision_id'], 'target':deepcopy(target),
            'criterion':deepcopy(criterion[0]), 'bundle':deepcopy(bundle), 'traces':traces,
            'material_ref':deepcopy(material['material_revision']), 'material_checksum':row['material_hash'],
            'ia_checksum':row['content_hash'], 'evidence_checksum':row['evidence_hash'],
            'material':deepcopy(material), 'evidence_analysis':deepcopy(analysis),
            'assessment_situation_ref':{'id':str(row['assessment_situation_id']),'checksum':row['snapshot_checksum']},
            'case_ref':deepcopy(row['snapshot_json']['case_ref']),
            'assessment_revision_id':observation['assessment_revision_id'],
            'evidence_revision_id':observation['evidence_revision_id']})
    return projections
