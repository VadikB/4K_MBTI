from __future__ import annotations

from typing import Literal

from pydantic import Field

from Api.m7_planning_contracts import StrictModel


class ReplaceRoutePositionRequest(StrictModel):
    expected_assessment_situation_id: str = Field(min_length=1)
    expected_state: Literal["active", "paused"]
    idempotency_key: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    policy_ref: dict


class GenerateEquivalentSituationRequest(StrictModel):
    expected_assessment_situation_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)
    provider_config_ref: dict
