from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentAdminUser, DBSession
from app.models.answer import CandidateAnswer
from app.models.sessions import CandidateSession
from app.schemas.admin import (
    AdminCandidateDetail,
    AdminCandidateListResponse,
    ManualScoreRequest,
    ManualScoreResponse,
)
from app.schemas.auth import AuthMessageResponse
from app.services.admin_service import AdminService
from app.services.processing_service import dispatch_session_processing


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
    try:
        parsed_session_id = int(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session id.") from exc

    session_row = await db.execute(
        select(CandidateSession)
        .where(CandidateSession.id == parsed_session_id)
        .options(selectinload(CandidateSession.answers).selectinload(CandidateAnswer.ai_evaluation))
    )
    session = session_row.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate session not found.")
    if session.submitted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session has not been submitted yet.",
        )

    for answer in session.answers:
        if answer.ai_evaluation is not None:
            await db.delete(answer.ai_evaluation)
            answer.ai_evaluation = None

    await db.commit()
    await dispatch_session_processing(parsed_session_id)
    return AuthMessageResponse(message="Session reprocessing requested. Updated results will appear shortly.")


@router.post("/answers/{answer_id}/reevaluate", response_model=AuthMessageResponse)
async def reevaluate_answer(answer_id: str, db: DBSession, _: CurrentAdminUser) -> AuthMessageResponse:
    try:
        parsed_answer_id = int(answer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid answer id.") from exc

    result = await db.execute(
        select(CandidateAnswer)
        .where(CandidateAnswer.id == parsed_answer_id)
        .options(
            selectinload(CandidateAnswer.session),
            selectinload(CandidateAnswer.ai_evaluation),
        )
    )
    answer = result.scalar_one_or_none()
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate answer not found.")
    if answer.session is None or answer.session.submitted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session has not been submitted yet.",
        )

    if answer.ai_evaluation is not None:
        await db.delete(answer.ai_evaluation)
        answer.ai_evaluation = None

    await db.commit()
    await dispatch_session_processing(int(answer.session_id))
    return AuthMessageResponse(message="Response reevaluation requested. Updated results will appear shortly.")


@router.delete("/candidates/{session_id}", response_model=AuthMessageResponse)
async def delete_candidate(session_id: str, db: DBSession, admin_user: CurrentAdminUser) -> AuthMessageResponse:
    await AdminService(db).delete_candidate(session_id=session_id, admin_email=admin_user.email)
    return AuthMessageResponse(message="Candidate session deleted.")
