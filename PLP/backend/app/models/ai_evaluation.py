from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, Numeric, TIMESTAMP, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.helpers import deserialize_text_list, serialize_text_list, utcnow


class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"

    id: Mapped[int] = mapped_column("ai_evaluation_id", Integer, primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_answers.answer_id"),
        index=True,
        unique=True,
        nullable=False,
    )
    total_score: Mapped[float | None] = mapped_column("score", Float, nullable=True)
    courtesy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    empathy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    respect_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tone_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    communication_clarity_score: Mapped[float | None] = mapped_column("communication_score", Float, nullable=True)
    _strengths_text: Mapped[str | None] = mapped_column("strengths", Text, nullable=True)
    _improvement_text: Mapped[str | None] = mapped_column("weakness", Text, nullable=True)
    final_summary: Mapped[str | None] = mapped_column("feedback", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow, nullable=False)

    answer = relationship("CandidateAnswer", back_populates="ai_evaluation")

    @property
    def strengths(self) -> list[str]:
        return deserialize_text_list(self._strengths_text)

    @strengths.setter
    def strengths(self, value: list[str] | str | None) -> None:
        self._strengths_text = serialize_text_list(value)

    @property
    def improvement_areas(self) -> list[str]:
        return deserialize_text_list(self._improvement_text)

    @improvement_areas.setter
    def improvement_areas(self, value: list[str] | str | None) -> None:
        self._improvement_text = serialize_text_list(value)

    @property
    def sympathy_score(self) -> float:
        return float(self.empathy_score or 0)

    @property
    def engagement_score(self) -> float:
        return float(self.communication_clarity_score or 0)

    @property
    def problem_handling_approach_score(self) -> float:
        return float(self.communication_clarity_score or 0)

    @property
    def confidence_score(self) -> None:
        return None

    @property
    def raw_response(self) -> dict:
        return {}


class AdminScore(Base):
    __tablename__ = "admin_evaluations"

    id: Mapped[int] = mapped_column("admin_id", Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_sessions.session_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    manual_score: Mapped[float | None] = mapped_column("admin_score", Float, nullable=True)
    notes: Mapped[str | None] = mapped_column("feedback", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column("updated_at", TIMESTAMP, default=utcnow, nullable=False)

    session = relationship("CandidateSession", back_populates="manual_scores")

    @property
    def admin_email(self) -> str:
        return getattr(self, "_admin_email", "admin")

    @admin_email.setter
    def admin_email(self, value: str) -> None:
        self._admin_email = value
