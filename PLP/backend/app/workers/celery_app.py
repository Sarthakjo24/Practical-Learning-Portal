from __future__ import annotations

import sys

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
    worker_prefetch_multiplier=1,
)

if sys.platform == "win32":
    # Default to a single-process worker on Windows for stability with
    # asyncio + aiomysql and native ML dependencies.
    celery_app.conf.update(
        worker_pool="solo",
        worker_concurrency=1,
    )
else:
    celery_app.conf.update(
        worker_concurrency=max(1, settings.eval_max_workers),
    )

# Import tasks to register them with Celery (after celery_app is defined)
from app.workers import tasks  # noqa: F401
