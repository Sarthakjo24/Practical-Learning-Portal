from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.api.deps import CurrentUser, DBSession
from app.schemas.candidate import (
    AnswerUploadResponse,
    CandidateSessionDetail,
    StartSessionRequest,
    StartSessionResponse,
    SubmitSessionResponse,
)
from app.services.audio_service import AudioService
from app.services.session_service import SessionService


router = APIRouter(prefix="/candidate", tags=["candidate"])


@router.post("/sessions", response_model=StartSessionResponse)
async def start_session(payload: StartSessionRequest, db: DBSession, user: CurrentUser) -> StartSessionResponse:
    service = SessionService(db)
    session = await service.start_session(user, payload.module_slug)
    return StartSessionResponse(**service.build_start_response(session))


@router.get("/sessions/{session_id}", response_model=CandidateSessionDetail)
async def get_session(session_id: str, db: DBSession, user: CurrentUser) -> CandidateSessionDetail:
    service = SessionService(db)
    session = await service.get_owned_session(user.id, session_id)
    return await service.build_session_detail(session)


@router.post(
    "/sessions/{session_id}/answers/{question_id}/audio",
    response_model=AnswerUploadResponse,
)
async def upload_audio(
    session_id: str,
    question_id: str,
    db: DBSession,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> AnswerUploadResponse:
    service = SessionService(db)
    answer = await service.upload_answer_audio(user.id, session_id, question_id, file)
    return AnswerUploadResponse(
        answer_id=str(answer.id),
        status=answer.status.value,
        audio_url=AudioService().candidate_audio_url(answer.audio_storage_key) or "",
    )


@router.post("/sessions/{session_id}/submit", response_model=SubmitSessionResponse)
async def submit_session(session_id: str, db: DBSession, user: CurrentUser) -> SubmitSessionResponse:
    session = await SessionService(db).submit_session(user.id, session_id)
    return SubmitSessionResponse(
        session_id=str(session.id),
        status=session.status.value,
        message="Responses submitted successfully.",
    )
