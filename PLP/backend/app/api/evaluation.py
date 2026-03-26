from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentAdminUser, DBSession
from app.schemas.evaluation import EvaluationConfigRead, EvaluationConfigUpdate
from app.services.module_service import ModuleService


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/configs/{module_slug}", response_model=EvaluationConfigRead)
async def get_evaluation_config(module_slug: str, db: DBSession, _: CurrentAdminUser) -> EvaluationConfigRead:
    module_service = ModuleService(db)
    module = await module_service.get_module_by_slug(module_slug)
    config = await module_service.get_active_evaluation_config(module.id)
    return EvaluationConfigRead(
        id=config.id,
        module_id=config.module_id,
        version=config.version,
        model_name=config.model_name,
        prompt_template=config.prompt_template,
        scoring_weights=config.scoring_weights,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.put("/configs/{module_slug}", response_model=EvaluationConfigRead)
async def update_evaluation_config(
    module_slug: str,
    payload: EvaluationConfigUpdate,
    db: DBSession,
    _: CurrentAdminUser,
) -> EvaluationConfigRead:
    config = await ModuleService(db).update_evaluation_config(module_slug, payload)
    return EvaluationConfigRead(
        id=config.id,
        module_id=config.module_id,
        version=config.version,
        model_name=config.model_name,
        prompt_template=config.prompt_template,
        scoring_weights=config.scoring_weights,
        is_active=config.is_active,
        created_at=config.created_at,
    )
