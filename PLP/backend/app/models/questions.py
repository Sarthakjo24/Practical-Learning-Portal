from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.helpers import utcnow


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(191))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    questions = relationship("Question", back_populates="module", cascade="all, delete-orphan")
    evaluation_configs = relationship(
        "EvaluationConfig",
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="desc(EvaluationConfig.version)",
    )
    sessions = relationship("CandidateSession", back_populates="module")


class EvaluationConfig(Base):
    __tablename__ = "evaluation_configs"
    __table_args__ = (UniqueConstraint("module_id", "version", name="uq_evaluation_configs_module_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id: Mapped[str] = mapped_column(String(36), ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_weights: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    module = relationship("Module", back_populates="evaluation_configs")
    evaluations = relationship("AIEvaluation", back_populates="evaluation_config")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("module_id", "question_code", name="uq_questions_module_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id: Mapped[str] = mapped_column(String(36), ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    question_code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(191), nullable=False)
    scenario_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    audio_storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    module = relationship("Module", back_populates="questions")
    standard_responses = relationship(
        "StandardResponse",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="StandardResponse.response_order",
    )
    session_questions = relationship("SessionQuestion", back_populates="question")
    answers = relationship("CandidateAnswer", back_populates="question")


class StandardResponse(Base):
    __tablename__ = "standard_responses"
    __table_args__ = (UniqueConstraint("question_id", "response_order", name="uq_standard_responses_question_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    response_order: Mapped[int] = mapped_column(Integer, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    question = relationship("Question", back_populates="standard_responses")
