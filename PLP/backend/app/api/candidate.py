from __future__ import annotations

from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

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
async def submit_session(
    session_id: str,
    request: Request,
    db: DBSession,
    user: CurrentUser,
) -> SubmitSessionResponse:
    service = SessionService(db)
    existing_session = await service.get_owned_session(user.id, session_id)
    if existing_session.submitted_at is not None:
        return SubmitSessionResponse(
            session_id=str(existing_session.id),
            status=existing_session.status.value,
            message="Responses already submitted.",
        )

    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        question_ids = [str(value) for value in form.getlist("question_ids")]
        files = [value for value in form.getlist("files") if isinstance(value, StarletteUploadFile)]

        if len(question_ids) != len(files):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each uploaded recording must include a matching question id.",
            )

        for question_id, file in zip(question_ids, files):
            await service.upload_answer_audio(user.id, session_id, question_id, file)

    session = await service.submit_session(user.id, session_id)
    return SubmitSessionResponse(
        session_id=str(session.id),
        status=session.status.value,
        message="Responses submitted successfully.",
    )
