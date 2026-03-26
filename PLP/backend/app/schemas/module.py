from __future__ import annotations

from pydantic import BaseModel


class ModuleSummary(BaseModel):
    id: str
    slug: str
    title: str
    description: str | None = None
    question_count: int
