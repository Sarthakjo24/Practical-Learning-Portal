from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.questions import EvaluationConfig, Module, Question
from app.schemas.evaluation import EvaluationConfigUpdate


class ModuleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active_modules(self) -> list[Module]:
        result = await self.db.execute(select(Module).where(Module.is_active.is_(True)).order_by(Module.title))
        return list(result.scalars().all())

    async def count_questions(self, module_id: int) -> int:
        result = await self.db.execute(select(func.count(Question.id)).where(Question.module_id == module_id))
        return int(result.scalar_one() or 0)

    async def count_questions_for_modules(self, module_ids: list[int]) -> dict[int, int]:
        if not module_ids:
            return {}
        result = await self.db.execute(
            select(Question.module_id, func.count(Question.id))
            .where(Question.module_id.in_(module_ids))
            .group_by(Question.module_id)
        )
        return {int(row[0]): int(row[1]) for row in result.all()}

    async def get_module_by_slug(self, module_slug: str) -> Module:
        modules = await self.list_active_modules()
        for module in modules:
            if module.slug == module_slug:
                return module
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")

    async def get_random_questions(self, module_id: int, limit: int) -> list[Question]:
        result = await self.db.execute(
            select(Question)
            .where(Question.module_id == module_id)
            .options(selectinload(Question.standard_responses))
            .order_by(func.rand())
            .limit(limit)
        )
        questions = list(result.scalars().all())
        if len(questions) < limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Module does not have {limit} questions.",
            )
        return questions

    async def get_active_evaluation_config(self, module_id: int) -> EvaluationConfig:
        result = await self.db.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.module_id == module_id)
            .order_by(EvaluationConfig.id.desc())
        )
        config = result.scalars().first()
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No evaluation configuration found for module.",
            )
        return config

    async def update_evaluation_config(self, module_slug: str, payload: EvaluationConfigUpdate) -> EvaluationConfig:
        module = await self.get_module_by_slug(module_slug)
        result = await self.db.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.module_id == module.id)
            .order_by(EvaluationConfig.id.desc())
        )
        config = result.scalars().first()

        if config is None:
            config = EvaluationConfig(module_id=module.id, prompt_template=payload.prompt_template)
            self.db.add(config)

        config.prompt_template = payload.prompt_template
        config.apply_scoring_weights(payload.scoring_weights)

        await self.db.commit()
        await self.db.refresh(config)
        return config
