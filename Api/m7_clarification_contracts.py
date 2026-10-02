from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)

class ClarificationQuestion(StrictModel):
    schema_version: Literal[1]
    admissible: bool
    text: str|None=None
    purpose: Literal["clarify_meaning","clarify_basis","clarify_contradiction"]|None=None
    indicator_ids: list[str]
    resolving_information: list[str]
    refusal_reason: str|None=None

class CreateClarificationRequest(StrictModel):
    c54_revision_id: str=Field(min_length=1)
    idempotency_key: str=Field(min_length=1,max_length=200)
    synthetic_material_confirmed: Literal[True]

class PresentClarificationRequest(StrictModel):
    expected_c54_revision_id: str=Field(min_length=1)

class ClarificationAnswerRequest(StrictModel):
    request_id: str=Field(min_length=1,max_length=200)
    turn_id: str=Field(min_length=1)
    content: str=Field(min_length=1,max_length=10000)

class ClarificationOutcomeRequest(StrictModel):
    request_id: str=Field(min_length=1,max_length=200)
    outcome: Literal["no_answer","refused"]
