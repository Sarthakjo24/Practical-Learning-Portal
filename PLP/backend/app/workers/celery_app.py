from __future__ import annotations

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "practical_learning_portal",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_default_queue="assessment",
    task_track_started=True,
    result_expires=3600,
)

# Import tasks to register them with Celery (after celery_app is defined)
from app.workers import tasks  # noqa: F401
