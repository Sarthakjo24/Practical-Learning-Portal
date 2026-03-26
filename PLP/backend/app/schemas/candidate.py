from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    module_slug: str = Field(min_length=2)


class CandidateSessionQuestion(BaseModel):
    question_id: str
    question_code: str
    title: str
    scenario_transcript: str
    audio_url: str
    display_order: int


class StartSessionResponse(BaseModel):
    session_id: str
    candidate_id: str
    module_slug: str
    module_title: str
    status: str
    questions: list[CandidateSessionQuestion]


class AnswerEvaluationBreakdown(BaseModel):
    total_score: float
    courtesy_score: float
    respect_score: float
    empathy_score: float
    sympathy_score: float
    tone_score: float
    communication_clarity_score: float
    engagement_score: float
    problem_handling_approach_score: float
    strengths: list[str]
    improvement_areas: list[str]
    final_summary: str
    confidence_score: float | None = None


class CandidateAnswerDetail(BaseModel):
    answer_id: str
    question_id: str
    question_code: str
    question_title: str
    display_order: int
    status: str
    question_audio_url: str
    audio_url: str | None = None
    transcript_text: str | None = None
    standard_responses: list[str] = []
    evaluation: AnswerEvaluationBreakdown | None = None


class CandidateSessionDetail(BaseModel):
    session_id: str
    candidate_id: str
    status: str
    module_slug: str
    module_title: str
    login_at: datetime
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    ai_score: float | None = None
    answers: list[CandidateAnswerDetail]


class AnswerUploadResponse(BaseModel):
    answer_id: str
    status: str
    audio_url: str


class SubmitSessionResponse(BaseModel):
    session_id: str
    status: str
    message: str
