from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.services.session_service import SessionService


def _db_stub():
    return SimpleNamespace(
        add=Mock(),
        execute=AsyncMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )


def _answer(answer_id=1, has_audio=True, question=None, evaluation=None):
    q = question or SimpleNamespace(
        id=9,
        question_code="Q-009",
        title="Question title",
        scenario_transcript="Scenario",
        audio_storage_key="q9.mp3",
    )
    return SimpleNamespace(
        id=answer_id,
        question_id=q.id,
        question=q,
        status=SimpleNamespace(value="completed"),
        audio_storage_key="audio.webm" if has_audio else "",
        transcript=SimpleNamespace(transcript_text="hello"),
        ai_evaluation=evaluation,
        created_at=datetime.utcnow(),
    )


class TestSessionServiceBehavior:
    @pytest.mark.asyncio
    async def test_start_session_rejects_when_no_questions(self):
        db = _db_stub()
        service = SessionService(db)
        service.module_service = SimpleNamespace(
            get_module_by_slug=AsyncMock(return_value=SimpleNamespace(id=1)),
            count_questions=AsyncMock(return_value=0),
            get_random_questions=AsyncMock(),
        )

        with pytest.raises(HTTPException) as exc:
            await service.start_session(SimpleNamespace(id=1), "slug")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_session_rejects_when_any_answer_missing_audio(self):
        db = _db_stub()
        service = SessionService(db)
        session = SimpleNamespace(id=1, answers=[_answer(1, has_audio=True), _answer(2, has_audio=False)])
        service.get_owned_session = AsyncMock(return_value=session)

        with pytest.raises(HTTPException) as exc:
            await service.submit_session(1, 1)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_session_commits_and_dispatches_when_complete(self, monkeypatch):
        db = _db_stub()
        service = SessionService(db)
        session = SimpleNamespace(id=1, answers=[_answer(1, True), _answer(2, True)], submitted_at=None)
        service.get_owned_session = AsyncMock(return_value=session)
        monkeypatch.setattr("app.services.session_service.dispatch_session_processing", AsyncMock(return_value="celery"))

        result = await service.submit_session(1, 1)
        assert result is session
        db.commit.assert_awaited_once()

    def test_serialize_evaluation_hides_failures_and_missing_scores(self):
        service = SessionService(_db_stub())
        assert service._serialize_evaluation(None) is None
        assert (
            service._serialize_evaluation(
                SimpleNamespace(total_score=None, final_summary="ok", courtesy_score=1, respect_score=1, empathy_score=1, sympathy_score=1, tone_score=1, communication_clarity_score=1, engagement_score=1, problem_handling_approach_score=1, strengths=[], improvement_areas=[], confidence_score=None)
            )
            is None
        )
        assert (
            service._serialize_evaluation(
                SimpleNamespace(total_score=8, final_summary="Evaluation failed: timeout", courtesy_score=1, respect_score=1, empathy_score=1, sympathy_score=1, tone_score=1, communication_clarity_score=1, engagement_score=1, problem_handling_approach_score=1, strengths=[], improvement_areas=[], confidence_score=None)
            )
            is None
        )

    def test_serialize_evaluation_returns_shape_for_valid_input(self):
        service = SessionService(_db_stub())
        data = service._serialize_evaluation(
            SimpleNamespace(
                total_score=8,
                final_summary="Strong answer",
                courtesy_score=7,
                respect_score=7,
                empathy_score=7,
                sympathy_score=7,
                tone_score=7,
                communication_clarity_score=7,
                engagement_score=7,
                problem_handling_approach_score=7,
                strengths=["A"],
                improvement_areas=["B"],
                confidence_score=0.9,
            )
        )
        assert data is not None
        assert data["total_score"] == 8.0
        assert data["final_summary"] == "Strong answer"

    def test_build_start_response_skips_missing_question(self):
        service = SessionService(_db_stub())
        service.audio_service = SimpleNamespace(question_audio_url=lambda key: f"/audio/{key}")
        session = SimpleNamespace(
            id=99,
            user=SimpleNamespace(candidate_code="C1"),
            module=SimpleNamespace(slug="m1", title="Module"),
            status=SimpleNamespace(value="started"),
            answers=[SimpleNamespace(id=1, question=None, question_id=5), _answer(2, True)],
        )
        payload = service.build_start_response(session)
        assert payload["session_id"] == "99"
        assert len(payload["questions"]) == 1
