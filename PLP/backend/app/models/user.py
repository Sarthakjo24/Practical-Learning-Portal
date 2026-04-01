from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column("user_id", Integer, primary_key=True, autoincrement=True)
    auth0_user_id: Mapped[str] = mapped_column("auth0_id", String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column("name", String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="candidate", nullable=False)

    sessions = relationship("CandidateSession", back_populates="user", cascade="all, delete-orphan")

    @property
    def candidate_code(self) -> str:
        return f"CAND-{int(self.id):05d}" if self.id is not None else "CAND-PENDING"

    @property
    def avatar_url(self) -> None:
        return None
