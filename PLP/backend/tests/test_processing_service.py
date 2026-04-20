from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import processing_service as svc


class _AsyncSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_celery_workers_available_true(monkeypatch):
    inspect = SimpleNamespace(ping=Mock(return_value={"worker": "pong"}))
    monkeypatch.setattr(svc.celery_app.control, "inspect", Mock(return_value=inspect))
    assert svc.celery_workers_available() is True


def test_celery_workers_available_false_on_exception(monkeypatch):
    monkeypatch.setattr(svc.celery_app.control, "inspect", Mock(side_effect=RuntimeError("boom")))
    assert svc.celery_workers_available() is False


def test_acquire_lock_and_attempt_helpers():
    redis = Mock()
    redis.set.return_value = True
    assert svc._acquire_requeue_lock(redis) is True
    assert svc._attempt_key(12).endswith(":12")


def test_should_skip_attempt_handles_values():
    redis = Mock()
    redis.get.return_value = b"100"
    assert svc._should_skip_attempt(redis, 1) is True
    redis.get.return_value = b"bad"
    assert svc._should_skip_attempt(redis, 1) is False
    redis.get.return_value = None
    assert svc._should_skip_attempt(redis, 1) is False


def test_record_attempt_sets_ttl_first_time():
    redis = Mock()
    redis.incr.return_value = 1
    svc._record_attempt(redis, 3)
    redis.expire.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_session_processing_uses_celery_when_available(monkeypatch):
    monkeypatch.setattr(svc.process_candidate_session, "delay", Mock())
    result = await svc.dispatch_session_processing(11, workers_available=True)
    assert result == "celery"


@pytest.mark.asyncio
async def test_dispatch_session_processing_falls_back_in_process(monkeypatch):
    monkeypatch.setattr(svc.process_candidate_session, "delay", Mock(side_effect=RuntimeError("fail")))

    def _consume_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(svc.asyncio, "create_task", _consume_task)
    result = await svc.dispatch_session_processing(11, workers_available=True)
    assert result == "in_process"


@pytest.mark.asyncio
async def test_enqueue_pending_processing_sessions_returns_zero_when_disabled(monkeypatch):
    monkeypatch.setattr(svc.settings, "eval_requeue_enabled", False)
    assert await svc.enqueue_pending_processing_sessions() == 0
    monkeypatch.setattr(svc.settings, "eval_requeue_enabled", True)


@pytest.mark.asyncio
async def test_enqueue_pending_processing_sessions_happy_path(monkeypatch):
    redis = Mock()
    redis.set.return_value = True
    redis.get.return_value = None
    redis.incr.return_value = 1
    monkeypatch.setattr(svc, "_get_redis", Mock(return_value=redis))
    monkeypatch.setattr(svc, "celery_workers_available", Mock(return_value=True))
    monkeypatch.setattr(svc, "dispatch_session_processing", AsyncMock(return_value="celery"))

    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(101, None), (102, None)]))
    )
    monkeypatch.setattr(svc, "AsyncSessionLocal", lambda: _AsyncSessionCtx(db))

    count = await svc.enqueue_pending_processing_sessions()
    assert count == 2


@pytest.mark.asyncio
async def test_run_processing_requeue_loop_runs_single_iteration(monkeypatch):
    monkeypatch.setattr(svc, "enqueue_pending_processing_sessions", AsyncMock(return_value=1))

    calls = {"count": 0}

    async def _sleep(_seconds):
        calls["count"] += 1
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(svc.asyncio, "sleep", _sleep)
    with pytest.raises(RuntimeError, match="stop-loop"):
        await svc.run_processing_requeue_loop(interval_seconds=1)
    assert calls["count"] == 1
