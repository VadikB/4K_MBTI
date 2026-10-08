from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProductCycleStartRequest(StrictModel):
    personalized_profile_id: int | None = Field(default=None, gt=0)
    idempotency_key: str = Field(min_length=1, max_length=200)
    selected_skills: list[Literal["K1", "K2", "K3", "K4"]] = ["K1", "K2", "K3", "K4"]


class ProductNextRequest(StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
