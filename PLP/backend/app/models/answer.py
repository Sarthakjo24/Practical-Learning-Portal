from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Integer, TIMESTAMP, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
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

    id: Mapped[int] = mapped_column("answer_id", Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_sessions.session_id"), index=True, nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.question_id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), index=True, nullable=False)
    audio_storage_key: Mapped[str] = mapped_column("audio_url", String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow, nullable=False)

    session = relationship("CandidateSession", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    transcript = relationship("Transcript", back_populates="answer", uselist=False, cascade="all, delete-orphan")
    ai_evaluation = relationship(
        "AIEvaluation",
        back_populates="answer",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def status(self) -> AnswerStatus:
        if self.ai_evaluation is not None:
            return AnswerStatus.EVALUATED
        if self.transcript is not None:
            return AnswerStatus.TRANSCRIBED
        if self.audio_storage_key:
            return AnswerStatus.RECORDED
        return AnswerStatus.PENDING

    @property
    def audio_duration_seconds(self) -> None:
        return None

    @property
    def submitted_at(self) -> datetime | None:
        if self.session is not None and self.session.submitted_at is not None:
            return self.session.submitted_at
        return self.created_at if self.audio_storage_key else None


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column("transcript_id", Integer, primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_answers.answer_id"), index=True, nullable=False)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow, nullable=False)

    answer = relationship("CandidateAnswer", back_populates="transcript")

    @property
    def detected_language(self) -> None:
        return None

    @property
    def model_name(self) -> str:
        return settings.faster_whisper_model

    @property
    def processing_seconds(self) -> None:
        return None
