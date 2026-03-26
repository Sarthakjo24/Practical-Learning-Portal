from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.helpers import utcnow


class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_answers.id", ondelete="CASCADE"), unique=True, index=True
    )
    evaluation_config_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evaluation_configs.id", ondelete="RESTRICT"), index=True
    )
    total_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    courtesy_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    respect_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    empathy_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    sympathy_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    tone_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    communication_clarity_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    engagement_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    problem_handling_approach_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    improvement_areas: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    final_summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    raw_response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    answer = relationship("CandidateAnswer", back_populates="ai_evaluation")
    evaluation_config = relationship("EvaluationConfig", back_populates="evaluations")


class AdminScore(Base):
    __tablename__ = "admin_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_sessions.id", ondelete="CASCADE"), index=True
    )
    admin_email: Mapped[str] = mapped_column(String(191), nullable=False)
    manual_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    session = relationship("CandidateSession", back_populates="manual_scores")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_type: Mapped[str] = mapped_column(String(50), index=True)
    actor_id: Mapped[str] = mapped_column(String(191), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[str] = mapped_column(String(191), index=True)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
