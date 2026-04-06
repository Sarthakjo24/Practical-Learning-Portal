from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base
from app.utils.helpers import slugify_text, trim_text, utcnow


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column("module_id", Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column("module_name", String(255), nullable=False)
    question_count: Mapped[int] = mapped_column("total_questions", Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    questions = relationship("Question", back_populates="module")
    evaluation_configs = relationship("EvaluationConfig", back_populates="module")
    sessions = relationship("CandidateSession", back_populates="module")

    @property
    def slug(self) -> str:
        return slugify_text(self.title)

    @property
    def description(self) -> None:
        return None


class EvaluationConfig(Base):
    __tablename__ = "evaluation_config"

    id: Mapped[int] = mapped_column("evaluation_config_id", Integer, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    prompt_template: Mapped[str] = mapped_column("prompt", Text, nullable=False)
    weight_courtesy: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    weight_empathy: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    weight_respect: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    weight_tone: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    weight_communication: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    module = relationship("Module", back_populates="evaluation_configs")

    @property
    def version(self) -> int:
        return 1

    @property
    def model_name(self) -> str:
        return settings.openai_model

    @property
    def scoring_weights(self) -> dict[str, float]:
        return {
            "courtesy": float(self.weight_courtesy or 0),
            "empathy": float(self.weight_empathy or 0),
            "respect": float(self.weight_respect or 0),
            "tone": float(self.weight_tone or 0),
            "communication": float(self.weight_communication or 0),
        }

    @property
    def is_active(self) -> bool:
        return True

    @property
    def created_at(self) -> datetime:
        return utcnow()

    def apply_scoring_weights(self, weights: dict[str, float]) -> None:
        self.weight_courtesy = float(weights.get("courtesy", self.weight_courtesy))
        self.weight_empathy = float(weights.get("empathy", self.weight_empathy))
        self.weight_respect = float(weights.get("respect", self.weight_respect))
        self.weight_tone = float(weights.get("tone", self.weight_tone))
        self.weight_communication = float(
            weights.get("communication", weights.get("communication_clarity", self.weight_communication))
        )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column("question_id", Integer, primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("modules.module_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    scenario_transcript: Mapped[str | None] = mapped_column("question_text", Text, nullable=True)
    audio_storage_key: Mapped[str] = mapped_column("audio_url", String(500), nullable=False)

    module = relationship("Module", back_populates="questions")
    standard_responses = relationship("StandardResponse", back_populates="question", order_by="StandardResponse.id")
    answers = relationship("CandidateAnswer", back_populates="question")

    @property
    def question_code(self) -> str:
        return f"Q-{int(self.id):03d}"

    @property
    def title(self) -> str:
        return trim_text(self.scenario_transcript, f"Question {self.id}")

    @property
    def is_active(self) -> bool:
        return True

    @property
    def audio_duration_seconds(self) -> None:
        return None


class StandardResponse(Base):
    __tablename__ = "standard_responses"

    id: Mapped[int] = mapped_column("standard_response_id", Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("questions.question_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    response_text: Mapped[str] = mapped_column(Text, nullable=False)

    question = relationship("Question", back_populates="standard_responses")

    @property
    def response_order(self) -> int:
        return int(self.id)

    @property
    def is_active(self) -> bool:
        return True
