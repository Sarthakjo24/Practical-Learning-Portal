from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_evaluation import AIEvaluation
from app.models.answer import CandidateAnswer, Transcript
from app.models.questions import Question
from app.models.sessions import CandidateSession
from app.services.evaluation_service import EvaluationService
from app.services.module_service import ModuleService
from app.services.transcription_service import TranscriptionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
_FAILURE_PREFIXES = (
    "evaluation failed:",
    "audio processing failed:",
)
_PARSE_FAILURE_MARKER = "unable to parse evaluation result."


@celery_app.task(
    name="app.workers.tasks.process_candidate_session",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_candidate_session(session_id: str) -> None:
    # On Windows the default ProactorEventLoop is incompatible with aiomysql.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_process_candidate_session(int(session_id)))


async def _process_candidate_session(session_id: int) -> None:
    # asyncio.run() creates a fresh event loop each call. Build a fresh async
    # SQLAlchemy engine per task so pooled connections stay bound to the same loop.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings as _settings

    engine = create_async_engine(_settings.database_url, pool_pre_ping=False)
    SessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        async with SessionLocal() as db:
            await _run_session_pipeline(db, session_id)
    finally:
        await engine.dispose()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []





def _needs_evaluation_refresh(answer: CandidateAnswer) -> bool:
    evaluation = answer.ai_evaluation
    if evaluation is None:
        return True

    summary = str(evaluation.final_summary or "").strip().lower()
    if not summary or summary.startswith(_FAILURE_PREFIXES) or summary == _PARSE_FAILURE_MARKER:
        return True
    if evaluation.total_score is None:
        return True
    return False


def _upsert_failed_evaluation(answer: CandidateAnswer, summary: str) -> None:
    if answer.ai_evaluation is None:
        answer.ai_evaluation = AIEvaluation(answer_id=answer.id)

    # Keep score fields NULL for retryable failures so requeue logic can pick
    # the session back up and produce a real AI evaluation later.
    answer.ai_evaluation.total_score = None
    answer.ai_evaluation.courtesy_score = None
    answer.ai_evaluation.respect_score = None
    answer.ai_evaluation.empathy_score = None
    answer.ai_evaluation.tone_score = None
    answer.ai_evaluation.communication_clarity_score = None
    answer.ai_evaluation.final_summary = summary
    answer.ai_evaluation.strengths = []
    answer.ai_evaluation.improvement_areas = []


def _upsert_zero_evaluation(answer: CandidateAnswer, summary: str) -> None:
    if answer.ai_evaluation is None:
        answer.ai_evaluation = AIEvaluation(answer_id=answer.id)

    answer.ai_evaluation.total_score = 0
    answer.ai_evaluation.courtesy_score = 0
    answer.ai_evaluation.respect_score = 0
    answer.ai_evaluation.empathy_score = 0
    answer.ai_evaluation.tone_score = 0
    answer.ai_evaluation.communication_clarity_score = 0
    answer.ai_evaluation.final_summary = summary
    answer.ai_evaluation.strengths = []
    answer.ai_evaluation.improvement_areas = []


async def _run_session_pipeline(db: AsyncSession, session_id: int) -> None:
    result = await db.execute(
        select(CandidateSession)
        .where(CandidateSession.id == session_id)
        .options(
            selectinload(CandidateSession.module),
            selectinload(CandidateSession.answers)
            .selectinload(CandidateAnswer.question)
            .selectinload(Question.standard_responses),
            selectinload(CandidateSession.answers).selectinload(CandidateAnswer.transcript),
            selectinload(CandidateSession.answers).selectinload(CandidateAnswer.ai_evaluation),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        return

    module_service = ModuleService(db)
    transcription_service = TranscriptionService()
    evaluation_service = EvaluationService()
    evaluation_config = await module_service.get_active_evaluation_config(session.module_id)

    for answer in session.answers:
        if not answer.audio_storage_key:
            _upsert_zero_evaluation(answer, "No audio recorded by candidate.")
            continue
        if answer.question is None:
            logger.warning(
                "Question metadata missing for answer %s (question_id=%s) in session %s.",
                answer.id,
                answer.question_id,
                session.id,
            )
            _upsert_failed_evaluation(
                answer,
                f"Evaluation failed: Question metadata missing for question_id={answer.question_id}.",
            )
            continue

        existing_transcript = str(answer.transcript.transcript_text or "").strip() if answer.transcript else ""
        needs_transcription = not existing_transcript
        needs_evaluation = _needs_evaluation_refresh(answer)

        if not needs_transcription and not needs_evaluation:
            continue

        transcript_text = existing_transcript
        if needs_transcription:
            try:
                transcript_payload = await transcription_service.transcribe(answer.audio_storage_key)
            except Exception as exc:
                logger.exception(
                    "Transcription failed for answer %s in session %s.",
                    answer.id,
                    session.id,
                )
                _upsert_failed_evaluation(answer, f"Audio processing failed: {exc}")
                continue

            transcript_text = str(transcript_payload.get("transcript_text") or "").strip()
            if answer.transcript is None:
                answer.transcript = Transcript(answer_id=answer.id, transcript_text=transcript_text)
            else:
                answer.transcript.transcript_text = transcript_text

        if not transcript_text:
            _upsert_failed_evaluation(
                answer,
                "Evaluation failed: Missing English/Hinglish transcript text.",
            )
            continue

        if not needs_evaluation:
            continue

        try:
            evaluation_payload = await evaluation_service.evaluate_answer(
                module=session.module,
                question=answer.question,
                transcript_text=transcript_text,
                evaluation_config=evaluation_config,
            )
        except Exception as exc:
            logger.exception(
                "Evaluation failed for answer %s in session %s.",
                answer.id,
                session.id,
            )
            _upsert_failed_evaluation(answer, f"Evaluation failed: {exc}")
            continue

        sentiment = evaluation_payload.get("sentiment_breakdown", {}) or {}
        handling = evaluation_payload.get("handling_breakdown", {}) or {}

        communication_clarity = _optional_float(handling.get("communication_clarity"))
        total_score = _optional_float(evaluation_payload.get("total_score"))
        courtesy = _optional_float(sentiment.get("courtesy"))
        respect = _optional_float(sentiment.get("respect"))
        empathy = _optional_float(sentiment.get("empathy"))
        tone = _optional_float(sentiment.get("tone"))
        strengths = _coerce_text_list(evaluation_payload.get("strengths"))
        improvement_areas = _coerce_text_list(evaluation_payload.get("improvement_areas"))
        final_summary = str(evaluation_payload.get("final_summary", "") or "").strip()

        if total_score is None:
            _upsert_failed_evaluation(
                answer,
                "Evaluation failed: Missing total_score in model output.",
            )
            continue

        if answer.ai_evaluation is None:
            answer.ai_evaluation = AIEvaluation(answer_id=answer.id)

        answer.ai_evaluation.total_score = total_score
        answer.ai_evaluation.courtesy_score = courtesy if courtesy is not None else _safe_float(sentiment.get("courtesy"))
        answer.ai_evaluation.respect_score = respect if respect is not None else _safe_float(sentiment.get("respect"))
        answer.ai_evaluation.empathy_score = empathy if empathy is not None else _safe_float(sentiment.get("empathy"))
        answer.ai_evaluation.tone_score = tone if tone is not None else _safe_float(sentiment.get("tone"))
        answer.ai_evaluation.communication_clarity_score = (
            communication_clarity
            if communication_clarity is not None
            else _safe_float(handling.get("communication_clarity"))
        )
        answer.ai_evaluation.final_summary = final_summary
        answer.ai_evaluation.strengths = strengths
        answer.ai_evaluation.improvement_areas = improvement_areas

    await db.commit()
