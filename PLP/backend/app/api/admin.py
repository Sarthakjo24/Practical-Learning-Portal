from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentAdminUser, DBSession
from app.schemas.admin import (
    AdminCandidateDetail,
    AdminCandidateListResponse,
    ManualScoreRequest,
    ManualScoreResponse,
)
from app.schemas.auth import AuthMessageResponse
from app.services.admin_service import AdminService


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/candidates", response_model=AdminCandidateListResponse)
async def list_candidates(
    db: DBSession,
    _: CurrentAdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    module_slug: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    candidate_id: str | None = None,
    email: str | None = None,
) -> AdminCandidateListResponse:
    return await AdminService(db).list_candidates(page, page_size, module_slug, status_filter, candidate_id, email)


@router.get("/candidates/{session_id}", response_model=AdminCandidateDetail)
async def get_candidate(session_id: str, db: DBSession, _: CurrentAdminUser) -> AdminCandidateDetail:
    return await AdminService(db).get_candidate_detail(session_id)


@router.put("/candidates/{session_id}/manual-score", response_model=ManualScoreResponse)
async def set_manual_score(
    session_id: str,
    payload: ManualScoreRequest,
    db: DBSession,
    admin_user: CurrentAdminUser,
) -> ManualScoreResponse:
    manual_score = await AdminService(db).create_manual_score(
        session_id=session_id,
        admin_email=admin_user.email,
        score=payload.manual_score,
        notes=payload.notes,
    )
    return ManualScoreResponse(
        id=str(manual_score.id),
        admin_email=manual_score.admin_email,
        manual_score=round(float(manual_score.manual_score), 2),
        notes=manual_score.notes,
        created_at=manual_score.created_at,
    )


@router.post("/candidates/{session_id}/reprocess", response_model=AuthMessageResponse)
async def reprocess_session(session_id: str, db: DBSession, _: CurrentAdminUser) -> AuthMessageResponse:
    from app.workers.tasks import _process_candidate_session, process_candidate_session
    import asyncio

    try:
        process_candidate_session.delay(session_id)
        return AuthMessageResponse(message="Reprocessing started for session.")
    except Exception:
        # Fallback to synchronous execution if Celery is not available
        asyncio.create_task(_process_candidate_session(int(session_id)))
        return AuthMessageResponse(message="Reprocessing started for session (synchronous fallback).")


@router.delete("/candidates/{session_id}", response_model=AuthMessageResponse)
async def delete_candidate(session_id: str, db: DBSession, admin_user: CurrentAdminUser) -> AuthMessageResponse:
    await AdminService(db).delete_candidate(session_id=session_id, admin_email=admin_user.email)
    return AuthMessageResponse(message="Candidate session deleted.")
