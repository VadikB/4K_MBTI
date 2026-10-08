"""Read-only resolution of saved recommendation inputs; no M6 reassessment."""
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


def resolve(connection, results: dict) -> dict:
    """Only server-loaded immutable revisions may reach this boundary."""
    payload = results['results']
    cycle_id = results['cycle_id']
    if payload.get('cycle_id') != cycle_id:
        raise ValueError('RECOMMENDATION_CYCLE_MISMATCH')
    calculation = connection.execute('SELECT c56_json,c56_hash FROM m6_cycle_calculations WHERE id=%s',
        (UUID(payload['c56_ref']['calculation_id']),)).fetchone()
    if not calculation:
        raise ValueError('RECOMMENDATION_CALCULATION_UNRESOLVED')
    _verified(calculation['c56_json'], calculation['c56_hash'])
    c56 = calculation['c56_json']
    for key in ('cycle_id', 'composition_checksum', 'observations', 'admissions'):
        if payload.get(key) != c56.get(key):
            raise ValueError('RECOMMENDATION_RESULTS_MISMATCH')
    ids = [x['revision_id'] for x in payload.get('observations', [])]
    if len(ids) != len(set(ids)):
        raise ValueError('RECOMMENDATION_AMBIGUOUS_IA')
    decisions = {d['indicator_id']: d for d in payload.get('admissions', [])}
    projections = []
    for observation in payload.get('observations', []):
        decision = decisions.get(observation['indicator_id'], {})
        if decision.get('schema_version') == 2 and observation['revision_id'] not in decision['interpretable_revision_ids']:
            continue
        # No-assessment entries are explicitly not IA; keep them as rejected candidates.
        if observation['revision_id'].startswith('non-numeric:'):
            continue
        row = connection.execute('''SELECT ir.content_json,ir.content_hash,ia.indicator_id,
            ar.id AS assessment_id,ar.output_json,ar.output_hash,q.input_json,q.input_hash,
            q.evidence_revision_id,er.output_json AS evidence_json,er.output_hash AS evidence_hash,
            eq.input_json AS material_json,eq.input_hash AS material_hash,
            s.assessment_situation_id,c.cycle_id
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
            raise ValueError('RECOMMENDATION_IA_UNRESOLVED')
        for value, digest in (('content_json','content_hash'),('output_json','output_hash'),
                              ('input_json','input_hash'),('evidence_json','evidence_hash'),('material_json','material_hash')):
            _verified(row[value], row[digest])
        for field, source in (('assessment_revision_id','assessment_id'),('evidence_revision_id','evidence_revision_id'),
                              ('assessment_situation_id','assessment_situation_id'),('indicator_id','indicator_id')):
            if observation[field] != str(row[source]):
                raise ValueError('RECOMMENDATION_REFERENCE_MISMATCH')
        if str(row['cycle_id']) != cycle_id:
            raise ValueError('RECOMMENDATION_CYCLE_MISMATCH')
        material, analysis, target = row['material_json'], row['evidence_json'], row['content_json']
        if material['cycle_id'] != cycle_id or material['as_id'] != observation['assessment_situation_id']:
            raise ValueError('RECOMMENDATION_MATERIAL_SCOPE')
        if row['input_json']['material'] != material or row['input_json']['evidence_analysis'] != analysis:
            raise ValueError('RECOMMENDATION_SOURCE_MISMATCH')
        validate_analysis(analysis, material)
        validate_assessment(row['output_json'], row['input_json'])
        matches = [x for x in row['output_json']['targets'] if x['indicator_id'] == observation['indicator_id']]
        if matches != [target]:
            raise ValueError('RECOMMENDATION_AMBIGUOUS_TARGET')
        for key in ('indicator_id','m2_version','status','outcome','opportunity','refs','confidence','contradictions'):
            if observation.get(key) != target.get(key):
                raise ValueError('RECOMMENDATION_OBSERVATION_MISMATCH')
        criterion = [x for x in material['criteria'] if x['id'] == target['indicator_id']]
        if len(criterion) != 1:
            raise ValueError('RECOMMENDATION_CRITERION_UNRESOLVED')
        bundles = [x for x in analysis['bundles'] if x['indicator_id'] == target['indicator_id']]
        if len(bundles) != 1:
            raise ValueError('RECOMMENDATION_BUNDLE_UNRESOLVED')
        bundle = bundles[0]
        # Resolve every reference through the accepted M6 snapshot down to material.
        traces = []
        for ref in target['refs']:
            if ref['kind'] in ('evidence','bundle'):
                if ref['kind'] == 'bundle' and ref['id'] != target['indicator_id']:
                    raise ValueError('RECOMMENDATION_CROSS_TARGET_BUNDLE')
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
                    raise ValueError('RECOMMENDATION_MATERIAL_UNRESOLVED')
                traces.append({'ref':deepcopy(ref), 'material':deepcopy(entries[0])})
        projections.append({'revision_id':observation['revision_id'], 'target':deepcopy(target),
            'criterion':deepcopy(criterion[0]), 'bundle':deepcopy(bundle), 'traces':traces,
            'material_ref':deepcopy(material['material_revision']), 'material_checksum':row['material_hash'],
            'ia_checksum':row['content_hash'], 'evidence_checksum':row['evidence_hash']})
    return {'cycle_id':cycle_id, 'results_revision_id':results['revision_id'],
            'results_checksum':checksum(payload), 'c56_checksum':calculation['c56_hash'], 'projections':projections}
