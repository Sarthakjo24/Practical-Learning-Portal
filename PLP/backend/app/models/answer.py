from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.helpers import utcnow


class AnswerStatus(str, enum.Enum):
    PENDING = "pending"
    RECORDED = "recorded"
    SUBMITTED = "submitted"
    TRANSCRIBED = "transcribed"
    EVALUATED = "evaluated"
    FAILED = "failed"


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_candidate_answers_session_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_sessions.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    status: Mapped[AnswerStatus] = mapped_column(Enum(AnswerStatus), default=AnswerStatus.PENDING, index=True)
    audio_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    session = relationship("CandidateSession", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    transcript = relationship("Transcript", back_populates="answer", uselist=False, cascade="all, delete-orphan")
    ai_evaluation = relationship(
        "AIEvaluation",
        back_populates="answer",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_answers.id", ondelete="CASCADE"), unique=True, index=True
    )
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    answer = relationship("CandidateAnswer", back_populates="transcript")
