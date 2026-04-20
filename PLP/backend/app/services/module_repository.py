from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.questions import EvaluationConfig, Module, Question


class ModuleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active_modules(self) -> list[Module]:
        result = await self.db.execute(select(Module).where(Module.is_active.is_(True)).order_by(Module.title))
        return list(result.scalars().all())

    async def list_questions_for_module(self, module_id: int) -> list[Question]:
        result = await self.db.execute(
            select(Question)
            .where(Question.module_id == module_id)
            .options(selectinload(Question.standard_responses))
        )
        return list(result.scalars().all())

    async def list_questions_for_modules(self, module_ids: list[int]) -> list[Question]:
        result = await self.db.execute(
            select(Question)
            .where(Question.module_id.in_(module_ids))
            .options(selectinload(Question.standard_responses))
        )
        return list(result.scalars().all())

    async def get_latest_evaluation_config(self, module_id: int) -> EvaluationConfig | None:
        result = await self.db.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.module_id == module_id)
            .order_by(EvaluationConfig.id.desc())
        )
        return result.scalars().first()
