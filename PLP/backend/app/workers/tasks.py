from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.ai_evaluation import AIEvaluation, AuditLog
from app.models.answer import AnswerStatus, CandidateAnswer, Transcript
from app.models.questions import Question
from app.models.sessions import CandidateSession, SessionStatus
from app.services.evaluation_service import EvaluationService
from app.services.module_service import ModuleService
from app.services.scoring_service import ScoringService
from app.services.transcription_service import TranscriptionService
from app.utils.helpers import utcnow
from app.workers.celery_app import celery_app


@celery_app.task(
    name="app.workers.tasks.process_candidate_session",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_candidate_session(session_id: str) -> None:
    asyncio.run(_process_candidate_session(session_id))


async def _process_candidate_session(session_id: str) -> None:
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

        try:
            evaluation_config = await module_service.get_active_evaluation_config(session.module_id)
            scores: list[float] = []

            for answer in session.answers:
                if not answer.audio_storage_key:
                    continue

                transcript_payload = await transcription_service.transcribe(answer.audio_storage_key)
                if answer.transcript is None:
                    answer.transcript = Transcript(
                        answer_id=answer.id,
                        transcript_text=transcript_payload["transcript_text"],
                        detected_language=transcript_payload["detected_language"],
                        model_name=transcript_payload["model_name"],
                        processing_seconds=transcript_payload["processing_seconds"],
                    )
                else:
                    answer.transcript.transcript_text = transcript_payload["transcript_text"]
                    answer.transcript.detected_language = transcript_payload["detected_language"]
                    answer.transcript.model_name = transcript_payload["model_name"]
                    answer.transcript.processing_seconds = transcript_payload["processing_seconds"]

                answer.status = AnswerStatus.TRANSCRIBED

                evaluation_payload = await evaluation_service.evaluate_answer(
                    module=session.module,
                    question=answer.question,
                    transcript_text=answer.transcript.transcript_text,
                    evaluation_config=evaluation_config,
                )

                sentiment = evaluation_payload.get("sentiment_breakdown", {})
                handling = evaluation_payload.get("handling_breakdown", {})
                values = {
                    "evaluation_config_id": evaluation_config.id,
                    "total_score": float(evaluation_payload.get("total_score", 0)),
                    "courtesy_score": float(sentiment.get("courtesy", 0)),
                    "respect_score": float(sentiment.get("respect", 0)),
                    "empathy_score": float(sentiment.get("empathy", 0)),
                    "sympathy_score": float(sentiment.get("sympathy", 0)),
                    "tone_score": float(sentiment.get("tone", 0)),
                    "communication_clarity_score": float(handling.get("communication_clarity", 0)),
                    "engagement_score": float(handling.get("engagement", 0)),
                    "problem_handling_approach_score": float(handling.get("problem_handling_approach", 0)),
                    "strengths": evaluation_payload.get("strengths", []),
                    "improvement_areas": evaluation_payload.get("improvement_areas", []),
                    "final_summary": evaluation_payload.get("final_summary", ""),
                    "confidence_score": (
                        float(evaluation_payload["confidence_score"])
                        if evaluation_payload.get("confidence_score") is not None
                        else None
                    ),
                    "raw_response": evaluation_payload,
                }

                if answer.ai_evaluation is None:
                    answer.ai_evaluation = AIEvaluation(answer_id=answer.id, **values)
                else:
                    for key, value in values.items():
                        setattr(answer.ai_evaluation, key, value)

                answer.status = AnswerStatus.EVALUATED
                scores.append(values["total_score"])

            session.ai_score = ScoringService.aggregate_session_score(scores)
            session.status = SessionStatus.COMPLETED
            session.completed_at = utcnow()
            session.error_message = None
            db.add(
                AuditLog(
                    actor_type="system",
                    actor_id="celery-worker",
                    action="session_evaluated",
                    entity_type="candidate_session",
                    entity_id=session.id,
                    metadata={"score": session.ai_score, "answers": len(session.answers)},
                )
            )
            await db.commit()
        except Exception as exc:
            session.status = SessionStatus.FAILED
            session.error_message = str(exc)[:500]
            db.add(
                AuditLog(
                    actor_type="system",
                    actor_id="celery-worker",
                    action="session_failed",
                    entity_type="candidate_session",
                    entity_id=session.id,
                    metadata={"error": session.error_message},
                )
            )
            await db.commit()
            raise
