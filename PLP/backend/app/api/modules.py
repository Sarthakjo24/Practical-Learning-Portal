from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DBSession
from app.schemas.module import ModuleSummary
from app.services.module_service import ModuleService


router = APIRouter(tags=["modules"])


@router.get("/health")
async def healthcheck() -> dict:
    return {"status": "ok", "service": "practical-learning-portal-api"}


@router.get("/modules", response_model=list[ModuleSummary])
async def list_modules(db: DBSession) -> list[ModuleSummary]:
    module_service = ModuleService(db)
    modules = await module_service.list_active_modules()
    question_counts = await module_service.count_questions_for_modules([module.id for module in modules])
    return [
        ModuleSummary(
            id=str(module.id),
            slug=module.slug,
            title=module.title,
            description=module.description,
            question_count=question_counts.get(module.id, 0),
        )
        for module in modules
    ]
