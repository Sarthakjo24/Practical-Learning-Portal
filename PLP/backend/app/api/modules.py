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
    modules = await ModuleService(db).list_active_modules()
    return [
        ModuleSummary(
            id=str(module.id),
            slug=module.slug,
            title=module.title,
            description=module.description,
            question_count=module.question_count,
        )
        for module in modules
    ]
