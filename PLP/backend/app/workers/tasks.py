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
            communication = float(
                handling.get("communication_clarity")
                or handling.get("engagement")
                or handling.get("problem_handling_approach")
                or 0
            )

            if answer.ai_evaluation is None:
                answer.ai_evaluation = AIEvaluation(
                    answer_id=answer.id,
                    total_score=float(evaluation_payload.get("total_score", 0)),
                    courtesy_score=float(sentiment.get("courtesy", 0)),
                    respect_score=float(sentiment.get("respect", 0)),
                    empathy_score=float(sentiment.get("empathy", 0)),
                    tone_score=float(sentiment.get("tone", 0)),
                    communication_clarity_score=communication,
                    final_summary=evaluation_payload.get("final_summary", ""),
                )
            else:
                answer.ai_evaluation.total_score = float(evaluation_payload.get("total_score", 0))
                answer.ai_evaluation.courtesy_score = float(sentiment.get("courtesy", 0))
                answer.ai_evaluation.respect_score = float(sentiment.get("respect", 0))
                answer.ai_evaluation.empathy_score = float(sentiment.get("empathy", 0))
                answer.ai_evaluation.tone_score = float(sentiment.get("tone", 0))
                answer.ai_evaluation.communication_clarity_score = communication
                answer.ai_evaluation.final_summary = evaluation_payload.get("final_summary", "")

            answer.ai_evaluation.strengths = evaluation_payload.get("strengths", [])
            answer.ai_evaluation.improvement_areas = evaluation_payload.get("improvement_areas", [])

        await db.commit()
