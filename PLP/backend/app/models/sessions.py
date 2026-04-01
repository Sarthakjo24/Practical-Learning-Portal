from __future__ import annotations

import enum
from datetime import datetime
from statistics import mean

from sqlalchemy import Integer, TIMESTAMP, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SessionStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CandidateSession(Base):
    __tablename__ = "candidate_sessions"

    id: Mapped[int] = mapped_column("session_id", Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), index=True, nullable=False)
    module_id: Mapped[int] = mapped_column(Integer, ForeignKey("modules.module_id"), index=True, nullable=False)
    auth0_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    login_at: Mapped[datetime] = mapped_column("login_time", TIMESTAMP, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column("submission_time", TIMESTAMP, nullable=True)

    user = relationship("User", back_populates="sessions")
    module = relationship("Module", back_populates="sessions")
    answers = relationship("CandidateAnswer", back_populates="session", cascade="all, delete-orphan")
    manual_scores = relationship(
        "AdminScore",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="desc(AdminScore.created_at)",
    )

    @property
    def status(self) -> SessionStatus:
        answers = list(self.answers or [])
        if self.submitted_at is None:
            return SessionStatus.IN_PROGRESS
        if answers and all(answer.ai_evaluation is not None for answer in answers):
            return SessionStatus.COMPLETED
        if any(answer.transcript is not None for answer in answers):
            return SessionStatus.PROCESSING
        return SessionStatus.SUBMITTED

    @property
    def started_at(self) -> datetime:
        return self.login_at

    @property
    def completed_at(self) -> datetime | None:
        created = [answer.ai_evaluation.created_at for answer in self.answers if answer.ai_evaluation is not None]
        return max(created) if created else None

    @property
    def ai_score(self) -> float | None:
        scores = [float(answer.ai_evaluation.total_score or 0) for answer in self.answers if answer.ai_evaluation]
        return round(mean(scores), 2) if scores else None

    @property
    def error_message(self) -> None:
        return None
