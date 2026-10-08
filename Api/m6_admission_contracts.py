"""Структура содержательного решения; не алгоритм семантической оценки."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Reference(Record):
    revision_id: str
    kind: Literal['turn', 'event', 'material', 'evidence', 'bundle', 'as_snapshot']
    id: str


class Finding(Record):
    feature: str = Field(min_length=1)
    analysis: str = Field(min_length=1)
    refs: list[Reference] = Field(min_length=1)
    consequence: str = Field(min_length=1)


class Individual(Record):
    revision_id: str
    status: Literal['ADMITTED', 'NOT_ADMITTED', 'INSUFFICIENT_MATERIAL']
    normative_basis: Finding
    opportunity: Finding
    independence: Finding
    clarification: Finding
    contradictions: Finding
    rationale: str = Field(min_length=1)
    limitations: list[str]


class Joint(Record):
    considered_revision_ids: list[str]
    status: Literal['COMPARABLE', 'NOT_COMPARABLE', 'INSUFFICIENT_MATERIAL']
    normative_meaning: Finding
    conditions: Finding
    contradictions: Finding
    rationale: str = Field(min_length=1)
    limitations: list[str]


def validate_refs(output, contexts):
    allowed = {}
    for context in contexts:
        material, analysis = context['material'], context['evidence_analysis']
        allowed[context['revision_id']] = {
            'turn': {x['turn_id'] for x in material['turns']},
            'event': {x['event_id'] for x in material['events']},
            'material': {x['material_id'] for x in material['materials']},
            'evidence': set(context['bundle']['evidence_ids']),
            'bundle': {context['target']['indicator_id']},
            'as_snapshot': {material['as_id']},
        }
    for finding in output.values():
        if isinstance(finding, dict) and 'refs' in finding:
            for ref in finding['refs']:
                if ref['id'] not in allowed.get(ref['revision_id'], {}).get(ref['kind'], set()):
                    raise ValueError('M6_ADMISSION_REFERENCE_INVALID')
    return output
