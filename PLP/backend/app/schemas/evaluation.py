from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvaluationConfigRead(BaseModel):
    id: str
    module_id: str
    version: int
    model_name: str
    prompt_template: str
    scoring_weights: dict[str, Any]
    is_active: bool
    created_at: datetime


class EvaluationConfigUpdate(BaseModel):
    prompt_template: str = Field(min_length=20)
    model_name: str = Field(default="gpt-4.1-mini", min_length=3)
    scoring_weights: dict[str, float]
    is_active: bool = True
