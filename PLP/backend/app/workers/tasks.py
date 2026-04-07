from __future__ import annotations

import asyncio

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
    asyncio.run(_process_candidate_session(int(session_id)))


async def _process_candidate_session(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
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
                continue

            transcript_payload = await transcription_service.transcribe(answer.audio_storage_key)
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
