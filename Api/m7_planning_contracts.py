from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CreateCyclePlanRequest(StrictModel):
    personalized_profile_id: int = Field(gt=0)
    selected_skills: list[Literal["K1", "K2", "K3", "K4"]] = ["K1", "K2", "K3", "K4"]
    time_budget_seconds: int | None = Field(default=None, gt=0)
    calendar_window_seconds: int | None = Field(default=None, gt=0)
    idempotency_key: str = Field(min_length=1, max_length=200)
    synthetic_material_confirmed: Literal[True]


class NextSituationRequest(StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_plan_revision_id: str = Field(min_length=1)
    synthetic_material_confirmed: Literal[True]


class PresentSituationRequest(StrictModel):
    expected_decision_revision: int = Field(gt=0)
