from __future__ import annotations
from typing import Any,Literal
from pydantic import BaseModel,ConfigDict,Field

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class CompletionRequest(StrictModel):
    action:Literal['complete','final_refusal','interrupt_for_continuation']
    reason:str=Field(min_length=1,max_length=1000)
    idempotency_key:str=Field(min_length=1,max_length=200)

class CycleControlRequest(StrictModel):
    action:Literal['pause','resume']
    reason:str=Field(min_length=1,max_length=1000)
    idempotency_key:str=Field(min_length=1,max_length=200)

class AdditionalSessionRequest(StrictModel):
    intent_id:str=Field(min_length=1)
    idempotency_key:str=Field(min_length=1,max_length=200)

class BlockingWaitRequest(StrictModel):
    operation_ref:str=Field(min_length=1,max_length=300)
    reason:str=Field(min_length=1,max_length=1000)

class ReconcileC46Request(StrictModel):
    expected_composition_checksum:str=Field(min_length=64,max_length=64)
    calculation_ref:dict[str,Any]
    coverage:dict[str,Any]
    skill_outcomes:list[dict[str,Any]]
