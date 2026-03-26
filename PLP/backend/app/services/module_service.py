from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.questions import EvaluationConfig, Module, Question
from app.schemas.evaluation import EvaluationConfigUpdate
from app.utils.helpers import utcnow


class ModuleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active_modules(self) -> list[Module]:
        result = await self.db.execute(select(Module).where(Module.is_active.is_(True)).order_by(Module.title))
        return list(result.scalars().all())

    async def get_module_by_slug(self, module_slug: str) -> Module:
        result = await self.db.execute(
            select(Module)
            .where(Module.slug == module_slug, Module.is_active.is_(True))
            .options(selectinload(Module.evaluation_configs))
        )
        module = result.scalar_one_or_none()
        if module is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")
        return module

    async def get_random_questions(self, module_id: str, limit: int) -> list[Question]:
        result = await self.db.execute(
            select(Question)
            .where(Question.module_id == module_id, Question.is_active.is_(True))
            .options(selectinload(Question.standard_responses))
            .order_by(func.rand())
            .limit(limit)
        )
        questions = list(result.scalars().all())
        if len(questions) < limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Module does not have {limit} active questions.",
            )
        return questions

    async def get_active_evaluation_config(self, module_id: str) -> EvaluationConfig:
        result = await self.db.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.module_id == module_id, EvaluationConfig.is_active.is_(True))
            .order_by(EvaluationConfig.version.desc())
        )
        config = result.scalars().first()
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No active evaluation configuration found for module.",
            )
        return config

    async def update_evaluation_config(self, module_slug: str, payload: EvaluationConfigUpdate) -> EvaluationConfig:
        module = await self.get_module_by_slug(module_slug)
        result = await self.db.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.module_id == module.id)
            .order_by(EvaluationConfig.version.desc())
        )
        current = result.scalars().first()

        if current is not None:
            await self.db.execute(
                update(EvaluationConfig)
                .where(EvaluationConfig.module_id == module.id, EvaluationConfig.is_active.is_(True))
                .values(is_active=False)
            )

        next_config = EvaluationConfig(
            module_id=module.id,
            version=current.version + 1 if current else 1,
            model_name=payload.model_name,
            prompt_template=payload.prompt_template,
            scoring_weights=payload.scoring_weights,
            is_active=payload.is_active,
            created_at=utcnow(),
        )
        self.db.add(next_config)
        await self.db.commit()
        await self.db.refresh(next_config)
        return next_config
