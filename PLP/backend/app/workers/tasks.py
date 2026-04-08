from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.ai_evaluation import AIEvaluation
from app.models.answer import CandidateAnswer, Transcript
from app.models.questions import Question
from app.models.sessions import CandidateSession
from app.services.evaluation_service import EvaluationService
from app.services.module_service import ModuleService
from app.services.transcription_service import TranscriptionService
from app.workers.celery_app import celery_app


@celery_app.task(
    name="app.workers.tasks.process_candidate_session",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_candidate_session(session_id: str) -> None:
    # On Windows the default ProactorEventLoop is incompatible with aiomysql —
    # the _proactor socket handle becomes None mid-write, raising AttributeError.
    # WindowsSelectorEventLoopPolicy uses SelectorEventLoop which works correctly.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_process_candidate_session(int(session_id)))


async def _process_candidate_session(session_id: int) -> None:
    # Create a FRESH engine for every task invocation.
    # asyncio.run() creates a new event loop each call; reusing the module-level
    # engine/pool (whose sockets are tied to the previous loop) causes:
    #   RuntimeError: Task got Future attached to a different loop
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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


async def _run_session_pipeline(db: object, session_id: int) -> None:
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
                # Provide a zeroed fallback evaluation for missing audio
                if answer.ai_evaluation is None:
                    answer.ai_evaluation = AIEvaluation(
                        answer_id=answer.id,
                        total_score=0,
                        courtesy_score=0,
                        respect_score=0,
                        empathy_score=0,
                        tone_score=0,
                        communication_clarity_score=0,
                        final_summary="No audio recorded by candidate."
                    )
                continue

            try:
                transcript_payload = await transcription_service.transcribe(answer.audio_storage_key)
            except Exception as e:
                # E.g., FileNotFoundError for old missing webm files
                if answer.ai_evaluation is None:
                    answer.ai_evaluation = AIEvaluation(
                        answer_id=answer.id,
                        total_score=0,
                        courtesy_score=0,
                        respect_score=0,
                        empathy_score=0,
                        tone_score=0,
                        communication_clarity_score=0,
                        final_summary=f"Audio processing failed: {str(e)}"
                    )
                continue

            if answer.transcript is None:
                answer.transcript = Transcript(
                    answer_id=answer.id,
                    transcript_text=transcript_payload["transcript_text"],
                )
            else:
                answer.transcript.transcript_text = transcript_payload["transcript_text"]

            evaluation_payload = await evaluation_service.evaluate_answer(
                module=session.module,
                question=answer.question,
                transcript_text=answer.transcript.transcript_text,
                evaluation_config=evaluation_config,
            )

            sentiment = evaluation_payload.get("sentiment_breakdown", {})
            handling = evaluation_payload.get("handling_breakdown", {})

            # Use explicit .get() per key — avoid or-chaining which treats valid 0 scores as falsy
            communication_clarity = float(handling.get("communication_clarity") or 0)

            total_score = float(evaluation_payload.get("total_score") or 0)
            courtesy = float(sentiment.get("courtesy") or 0)
            respect = float(sentiment.get("respect") or 0)
            empathy = float(sentiment.get("empathy") or 0)
            tone = float(sentiment.get("tone") or 0)
            final_summary = evaluation_payload.get("final_summary", "") or ""

            if answer.ai_evaluation is None:
                answer.ai_evaluation = AIEvaluation(
                    answer_id=answer.id,
                    total_score=total_score,
                    courtesy_score=courtesy,
                    respect_score=respect,
                    empathy_score=empathy,
                    tone_score=tone,
                    communication_clarity_score=communication_clarity,
                    final_summary=final_summary,
                )
            else:
                answer.ai_evaluation.total_score = total_score
                answer.ai_evaluation.courtesy_score = courtesy
                answer.ai_evaluation.respect_score = respect
                answer.ai_evaluation.empathy_score = empathy
                answer.ai_evaluation.tone_score = tone
                answer.ai_evaluation.communication_clarity_score = communication_clarity
                answer.ai_evaluation.final_summary = final_summary

            answer.ai_evaluation.strengths = evaluation_payload.get("strengths", []) or []
            answer.ai_evaluation.improvement_areas = evaluation_payload.get("improvement_areas", []) or []

        await db.commit()
