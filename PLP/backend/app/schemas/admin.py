from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.schemas.candidate import CandidateAnswerDetail


class AdminCandidateListItem(BaseModel):
    session_id: str
    candidate_id: str
    name: str
    email: EmailStr
    module_title: str
    status: str
    ai_score: float | None = None
    evaluator_score: float | None = None
    submission_time: datetime | None = None
    login_time: datetime


class AdminCandidateListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[AdminCandidateListItem]


class ManualScoreRequest(BaseModel):
    manual_score: float = Field(ge=0, le=100)
    notes: str | None = None


class ManualScoreResponse(BaseModel):
    id: str
    admin_email: str
    manual_score: float
    notes: str | None = None
    created_at: datetime


class AdminCandidateDetail(BaseModel):
    session_id: str
    candidate_id: str
    name: str
    email: EmailStr
    module_slug: str
    module_title: str
    status: str
    ai_score: float | None = None
    overall_performance_summary: str | None = None
    overall_ai_total_score: float | None = None
    overall_strengths: list[str] | None = None
    overall_weaknesses: list[str] | None = None
    question_wise_scores: list[dict[str, Any]] | None = None
    latest_manual_score: ManualScoreResponse | None = None
    login_time: datetime
    submission_time: datetime | None = None
    completed_at: datetime | None = None
    answers: list[CandidateAnswerDetail]

