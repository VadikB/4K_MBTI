"""PM-05: substantive admission over saved final revisions, never client flags."""
from __future__ import annotations

import json
from collections import defaultdict

from Api.assessment_configuration import definition_checksum
from Api.m5_rule_engine import _call_with_trace, _gateway_for
from Api.m6_admission_contracts import Individual, Joint, validate_refs
from Api.m6_admission_material import resolve
from Api.m6_admission_package import load_mechanism, verify_mechanism

VERSION = 'm6_substantive_admission/2.0.0'


def evaluate(stage, contexts, mechanism, *, gateway=None):
    verify_mechanism(mechanism, definition_checksum(mechanism))
    value = {'stage': stage, 'contexts': contexts}
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > mechanism['max_input_bytes']:
        raise ValueError('M6_ADMISSION_CONTEXT_LIMIT')
    resolved = _gateway_for(mechanism['operation'], gateway)
    if not resolved.enabled:
        raise ValueError('M6_ADMISSION_GATEWAY_UNAVAILABLE')
    messages = [
        {'role': 'system', 'content': mechanism['prompt'] + '\nJSON Schema:\n' + json.dumps(mechanism['schema'][stage])},
        {'role': 'user', 'content': encoded},
    ]
    raw, trace = _call_with_trace(resolved, messages, operation=mechanism['operation'],
                                routing_key='m6-admission:' + definition_checksum(value))
    if trace['identity_status'] != 'sent_matches_snapshot':
        raise ValueError('M6_ADMISSION_AI_IDENTITY_MISMATCH')
    schema = Individual if stage == 'individual' else Joint
    output = validate_refs(schema.model_validate_json(raw).model_dump(), contexts)
    ids = [x['revision_id'] for x in contexts]
    actual = [output['revision_id']] if stage == 'individual' else output['considered_revision_ids']
    if sorted(actual) != sorted(ids):
        raise ValueError('M6_ADMISSION_COMPOSITION_MISMATCH')
    return {**output, 'ai_trace': trace, 'input_checksum': definition_checksum(value)}


def _failure(exc):
    # Do not persist provider messages, material or credentials in exception text.
    code = str(exc)
    return code if (code.startswith('M6_') or code in {'CHECKSUM_MISMATCH', 'SOURCE_UNRESOLVED', 'TARGET_SET_MISMATCH'}) and code.replace('_', '').isalnum() else type(exc).__name__


def decide(connection, *, cycle_id: str, observations: list[dict], gateway=None) -> tuple[str, list[dict], list[str]]:
    mechanism = load_mechanism(VERSION)
    by_indicator = defaultdict(list)
    seen = set()
    for item in observations:
        identity = (item['indicator_id'], item['assessment_situation_id'])
        if identity in seen:
            raise ValueError('M6_ADMISSION_AMBIGUOUS_REVISION')
        seen.add(identity)
        by_indicator[item['indicator_id']].append(item)
    requirements = connection.execute(
        '''SELECT p.observation_requirements_json FROM m7_cycle_plans p
           JOIN m5_cycles c ON c.id=p.cycle_db_id WHERE c.cycle_id=%s''', (cycle_id,),
    ).fetchone()
    requirement_map = {x['indicator_id']: x for x in (requirements['observation_requirements_json'] if requirements else [])}
    decisions, limitations = [], []
    for indicator, rows in sorted(by_indicator.items()):
        individual, contexts, admitted = [], [], []
        for observation in sorted(rows, key=lambda x: x['revision_id']):
            rid = observation['revision_id']
            if observation.get('outcome') not in {'L0', 'L1', 'L2', 'L3'}:
                individual.append({'revision_id': rid, 'status': 'PROCESSING_FAILED' if observation.get('status') == 'TECHNICAL_FAILURE' else 'NOT_NUMERIC_IA',
                                   'reason_code': observation.get('status', 'NO_NUMERIC_OUTCOME')})
                continue
            try:
                context = resolve(connection, cycle_id=cycle_id, observations=[observation])[0]
            except (ValueError, KeyError, IndexError) as exc:
                individual.append({'revision_id': rid, 'status': 'MATERIAL_INVALID', 'reason_code': _failure(exc)})
                continue
            contexts.append(context)
            try:
                result = evaluate('individual', [context], mechanism, gateway=gateway)
            except Exception as exc:
                result = {'revision_id': rid, 'status': 'PROCESSING_FAILED', 'reason_code': _failure(exc)}
            individual.append(result)
            if result['status'] == 'ADMITTED':
                admitted.append(context)
        interpreted = sorted(x['revision_id'] for x in admitted)
        unresolved = any(x['status'] in {'PROCESSING_FAILED', 'MATERIAL_INVALID', 'INSUFFICIENT_MATERIAL'} for x in individual)
        if unresolved:
            joint = {'status': 'INPUT_NOT_READY', 'reason_code': 'M6_ADMISSION_INDIVIDUAL_UNRESOLVED'}
        elif admitted:
            # Different normative packages require an explicitly approved mapping; none is installed.
            identities = {(x['criterion']['m2_version'], x['criterion']['package_sha256']) for x in admitted}
            if len(identities) != 1:
                joint = {'status': 'MATERIAL_INVALID', 'reason_code': 'M6_ADMISSION_M2_MAPPING_UNVERIFIED'}
            else:
                try:
                    joint = evaluate('joint', admitted, mechanism, gateway=gateway)
                except Exception as exc:
                    joint = {'status': 'PROCESSING_FAILED', 'reason_code': _failure(exc)}
        else:
            joint = {'status': 'NO_INTERPRETABLE_IA'}
        requirement = requirement_map.get(indicator)
        required = requirement.get('distinct_as_required') if requirement else None
        count = len({x['material']['as_id'] for x in admitted})
        sufficient = type(required) is int and required > 0 and count >= required
        numeric = joint['status'] == 'COMPARABLE' and sufficient
        reason = ('ADMITTED' if numeric else 'SUFFICIENCY_NOT_ESTABLISHED'
                  if joint['status'] == 'COMPARABLE' else joint['status'])
        decision = {
            'schema_version': 2, 'cycle_id': cycle_id, 'indicator_id': indicator,
            'considered_revision_ids': sorted(x['revision_id'] for x in rows),
            'interpretable_revision_ids': interpreted,
            'included_revision_ids': interpreted if numeric else [],
            'excluded_revision_ids': sorted(x['revision_id'] for x in rows if not numeric or x['revision_id'] not in interpreted),
            'interpretation_admissible': bool(interpreted), 'numeric_admissible': numeric,
            'reason_code': reason, 'individual': individual, 'joint': joint,
            'processing_status': 'failed' if joint['status'] == 'PROCESSING_FAILED' or
                any(x['status'] == 'PROCESSING_FAILED' for x in individual) else 'completed',
            'sufficiency': {'requirement': requirement, 'distinct_as_count': count, 'met': sufficient},
            'source': mechanism['manifest']['source'],
            'mechanism_ref': {'ref': VERSION, 'checksum': definition_checksum(mechanism)},
            'mechanism': {'ref': VERSION, 'checksum': definition_checksum(mechanism), 'snapshot': mechanism},
            'contexts': contexts,
        }
        decisions.append(decision)
        for item in individual:
            limitations.extend(f'{indicator}: {text}' for text in item.get('limitations', []))
        limitations.extend(f'{indicator}: {text}' for text in joint.get('limitations', []))
        if not numeric:
            limitations.append(f'{indicator}: {reason}; ' + joint.get('rationale', joint.get('reason_code', reason)))
    return VERSION, decisions, limitations
