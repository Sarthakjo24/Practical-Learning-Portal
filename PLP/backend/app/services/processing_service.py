from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from redis import Redis
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.ai_evaluation import AIEvaluation
from app.models.answer import CandidateAnswer
from app.models.sessions import CandidateSession
from app.utils.helpers import utcnow
from app.workers.celery_app import celery_app
from app.workers.tasks import _process_candidate_session, process_candidate_session

logger = logging.getLogger(__name__)
_KEY_PREFIX = "plp:eval:requeue"
_LOCK_KEY = f"{_KEY_PREFIX}:lock"


def celery_workers_available(timeout_seconds: float = 1.0) -> bool:
    try:
        inspector = celery_app.control.inspect(timeout=timeout_seconds)
        return bool(inspector.ping() or {})
    except Exception:
        logger.exception("Failed to inspect Celery worker health.")
        return False


def _get_redis() -> Redis:
    return Redis.from_url(settings.redis_url)


def _acquire_requeue_lock(redis_conn: Redis) -> bool:
    ttl = max(5, settings.eval_requeue_lock_ttl_seconds)
    return bool(redis_conn.set(_LOCK_KEY, "1", nx=True, ex=ttl))


def _attempt_key(session_id: int) -> str:
    return f"{_KEY_PREFIX}:attempts:{session_id}"


def _should_skip_attempt(redis_conn: Redis, session_id: int) -> bool:
    max_attempts = max(1, settings.eval_requeue_max_attempts)
    raw = redis_conn.get(_attempt_key(session_id))
    if raw is None:
        return False
    try:
        return int(raw) >= max_attempts
    except (TypeError, ValueError):
        return False


def _record_attempt(redis_conn: Redis, session_id: int) -> None:
    key = _attempt_key(session_id)
    count = redis_conn.incr(key)
    if count == 1:
        ttl = max(300, settings.eval_requeue_attempt_ttl_seconds)
        redis_conn.expire(key, ttl)


async def dispatch_session_processing(session_id: int, *, workers_available: bool | None = None) -> str:
    sid = int(session_id)
    should_use_celery = workers_available if workers_available is not None else celery_workers_available()

    if should_use_celery:
        try:
            process_candidate_session.delay(str(sid))
            return "celery"
        except Exception:
            logger.exception(
                "Celery dispatch failed for session %s. Falling back to in-process background task.",
                sid,
            )
    else:
        logger.warning(
            "No active Celery workers detected for session %s. Running in-process background task.",
            sid,
        )

    asyncio.create_task(_process_candidate_session(sid))
    return "in_process"


async def enqueue_pending_processing_sessions() -> int:
    if not settings.eval_requeue_enabled:
        return 0

    try:
        redis_conn = _get_redis()
        if not _acquire_requeue_lock(redis_conn):
            return 0
    except Exception:
        logger.exception("Unable to acquire processing requeue lock; skipping this cycle.")
        return 0

    cutoff = utcnow() - timedelta(seconds=max(1, settings.eval_requeue_session_age_seconds))
    async with AsyncSessionLocal() as db:
        missing_strengths = or_(
            AIEvaluation._strengths_text.is_(None),
            AIEvaluation._strengths_text == "",
            AIEvaluation._strengths_text == "[]",
        )
        missing_weaknesses = or_(
            AIEvaluation._improvement_text.is_(None),
            AIEvaluation._improvement_text == "",
            AIEvaluation._improvement_text == "[]",
        )
        missing_summary = or_(
            AIEvaluation.final_summary.is_(None),
            AIEvaluation.final_summary == "",
        )

        result = await db.execute(
            select(CandidateSession.id, CandidateSession.submitted_at)
            .join(CandidateSession.answers)
            .outerjoin(CandidateAnswer.ai_evaluation)
            .where(
                CandidateSession.submitted_at.isnot(None),
                CandidateSession.submitted_at <= cutoff,
                CandidateAnswer.audio_storage_key != "",
                or_(
                    AIEvaluation.id.is_(None),
                    AIEvaluation.total_score.is_(None),
                    missing_strengths,
                    missing_weaknesses,
                    missing_summary,
                    AIEvaluation.final_summary.like("Evaluation failed:%"),
                    AIEvaluation.final_summary.like("Audio processing failed:%"),
                    AIEvaluation.final_summary == "Unable to parse evaluation result.",
                ),
            )
            .group_by(CandidateSession.id, CandidateSession.submitted_at)
            .order_by(CandidateSession.submitted_at.asc())
            .limit(max(1, settings.eval_requeue_batch_size))
        )
        session_ids = [int(row[0]) for row in result.all()]
        workers_online = celery_workers_available()
        enqueued = 0

        for session_id in session_ids:
            if _should_skip_attempt(redis_conn, session_id):
                continue
            mode = await dispatch_session_processing(session_id, workers_available=workers_online)
            if mode:
                _record_attempt(redis_conn, session_id)
                enqueued += 1

        return enqueued


async def run_processing_requeue_loop(interval_seconds: int | None = None) -> None:
    sleep_seconds = interval_seconds or settings.eval_requeue_interval_seconds
    while True:
        try:
            count = await enqueue_pending_processing_sessions()
            if count:
                logger.info("Requeued %s pending transcription/evaluation sessions.", count)
        except Exception:
            logger.exception("Processing requeue loop failed.")
        await asyncio.sleep(max(10, sleep_seconds))
