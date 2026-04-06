from __future__ import annotations

import asyncio
import logging

from sqlalchemy import distinct, select

from app.core.database import AsyncSessionLocal
from app.models.ai_evaluation import AIEvaluation
from app.models.answer import CandidateAnswer
from app.models.sessions import CandidateSession
from app.workers.tasks import _process_candidate_session, process_candidate_session

logger = logging.getLogger(__name__)


async def enqueue_pending_processing_sessions() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(distinct(CandidateSession.id))
            .join(CandidateSession.answers)
            .outerjoin(CandidateAnswer.ai_evaluation)
            .where(
                CandidateSession.submitted_at.isnot(None),
                CandidateAnswer.audio_storage_key != "",
                AIEvaluation.id.is_(None),
            )
        )
        session_ids = [str(row[0]) for row in result.all()]

        for session_id in session_ids:
            try:
                process_candidate_session.delay(session_id)
            except Exception:
                logger.exception(
                    "Failed to enqueue pending processing task for session %s; running in-process fallback.",
                    session_id,
                )
                asyncio.create_task(_process_candidate_session(int(session_id)))

        return len(session_ids)


async def run_processing_requeue_loop(interval_seconds: int = 300) -> None:
    while True:
        try:
            count = await enqueue_pending_processing_sessions()
            if count:
                logger.info("Requeued %s pending transcription/evaluation sessions.", count)
        except Exception:
            logger.exception("Processing requeue loop failed.")
        await asyncio.sleep(interval_seconds)
