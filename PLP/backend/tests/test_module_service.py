from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.services.module_service import ModuleService


def _std(text="response", active=True):
    return SimpleNamespace(response_text=text, is_active=active)


def _question(question_id, module_id=1, audio_storage_key="q.mp3", standard_responses=None, scenario_transcript="ctx"):
    return SimpleNamespace(
        id=question_id,
        module_id=module_id,
        audio_storage_key=audio_storage_key,
        standard_responses=standard_responses if standard_responses is not None else [_std()],
        scenario_transcript=scenario_transcript,
        title=f"Question {question_id}",
    )


def _db_with_scalars(items):
    scalars = SimpleNamespace(all=lambda: items, first=lambda: items[0] if items else None)
    return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: scalars)))


def _service_with_repo(*, repo=None, audio_service=None):
    db = SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
    repository = repo or SimpleNamespace(
        list_active_modules=AsyncMock(return_value=[]),
        list_questions_for_module=AsyncMock(return_value=[]),
        list_questions_for_modules=AsyncMock(return_value=[]),
        get_latest_evaluation_config=AsyncMock(return_value=None),
    )
    audio = audio_service or SimpleNamespace(
        has_question_audio=lambda _: True,
        question_audio_url=lambda key: f"/assets/{key}",
    )
    return ModuleService(db, repository=repository, audio_service=audio), db, repository


class TestModuleServiceHelpers:
    @pytest.mark.asyncio
    async def test_list_active_modules_returns_query_results_in_order(self):
        modules = [SimpleNamespace(id=1, title="A"), SimpleNamespace(id=2, title="B")]
        service = ModuleService(_db_with_scalars(modules))
        result = await service.list_active_modules()
        assert result == modules

    def test_active_standard_response_count_counts_non_blank_active_only(self):
        service = ModuleService(SimpleNamespace())
        responses = [_std("ok", True), _std("   ", True), _std("inactive", False), _std("another", True)]
        assert service._active_standard_response_count(responses) == 2

    def test_is_eligible_question_requires_audio_and_active_standard_response(self, monkeypatch):
        service = ModuleService(SimpleNamespace())
        monkeypatch.setattr(service.audio_service, "has_question_audio", lambda _: True)
        assert service._is_eligible_question(_question(1, standard_responses=[_std("ok", True)])) is True
        assert service._is_eligible_question(_question(2, standard_responses=[_std("", True)])) is False

    def test_dedupe_questions_by_audio_prefers_higher_priority_variant(self, monkeypatch):
        service = ModuleService(SimpleNamespace())
        monkeypatch.setattr(service.audio_service, "question_audio_url", lambda key: f"/assets/{key}")

        lower = _question(1, audio_storage_key="shared.mp3", standard_responses=[_std("one", True)])
        higher = _question(
            2,
            audio_storage_key="folder/shared.mp3",
            standard_responses=[_std("one", True), _std("two", True)],
            scenario_transcript="longer transcript text",
        )
        unique = _question(3, audio_storage_key="unique.mp3")
        deduped = service._dedupe_questions_by_audio([lower, higher, unique])

        assert [item.id for item in deduped] == [2, 3]

    def test_question_priority_reflects_standard_count_path_and_transcript(self):
        service = ModuleService(SimpleNamespace())
        q_a = _question(1, audio_storage_key="a.mp3", standard_responses=[_std("one", True)], scenario_transcript="x")
        q_b = _question(
            2,
            audio_storage_key="folder/a.mp3",
            standard_responses=[_std("one", True), _std("two", True)],
            scenario_transcript="xyz",
        )
        assert service._question_priority(q_b) > service._question_priority(q_a)


class TestModuleServiceBehavior:
    @pytest.mark.asyncio
    async def test_count_questions_returns_deduped_eligible_count(self, monkeypatch):
        questions = [
            _question(1, audio_storage_key="same.mp3", standard_responses=[_std("ok", True)]),
            _question(2, audio_storage_key="same.mp3", standard_responses=[_std("ok", True), _std("also", True)]),
            _question(3, audio_storage_key="noaudio.mp3", standard_responses=[_std("ok", True)]),
        ]
        service = ModuleService(_db_with_scalars(questions))
        monkeypatch.setattr(service.audio_service, "has_question_audio", lambda key: key != "noaudio.mp3")
        monkeypatch.setattr(service.audio_service, "question_audio_url", lambda key: f"/assets/{key}")

        result = await service.count_questions(module_id=1)
        assert result == 1

    @pytest.mark.asyncio
    async def test_count_questions_for_modules_returns_zero_map_for_empty_ids(self):
        service = ModuleService(SimpleNamespace())
        assert await service.count_questions_for_modules([]) == {}

    @pytest.mark.asyncio
    async def test_get_module_by_slug_raises_404_when_not_found(self):
        service = ModuleService(SimpleNamespace())
        service.list_active_modules = AsyncMock(return_value=[SimpleNamespace(slug="abc")])

        with pytest.raises(HTTPException) as exc:
            await service.get_module_by_slug("missing")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_module_by_slug_returns_matching_module(self):
        service = ModuleService(SimpleNamespace())
        module = SimpleNamespace(slug="target")
        service.list_active_modules = AsyncMock(return_value=[SimpleNamespace(slug="other"), module])

        result = await service.get_module_by_slug("target")
        assert result is module

    @pytest.mark.asyncio
    async def test_get_random_questions_raises_when_limit_exceeds_eligible(self, monkeypatch):
        questions = [_question(1, audio_storage_key="q1.mp3")]
        service = ModuleService(_db_with_scalars(questions))
        monkeypatch.setattr(service.audio_service, "has_question_audio", lambda _: True)
        monkeypatch.setattr(service.audio_service, "question_audio_url", lambda key: f"/assets/{key}")

        with pytest.raises(HTTPException) as exc:
            await service.get_random_questions(module_id=1, limit=2)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_random_questions_samples_when_more_than_limit(self, monkeypatch):
        questions = [_question(1, audio_storage_key="a.mp3"), _question(2, audio_storage_key="b.mp3"), _question(3, audio_storage_key="c.mp3")]
        service = ModuleService(_db_with_scalars(questions))
        monkeypatch.setattr(service.audio_service, "has_question_audio", lambda _: True)
        monkeypatch.setattr(service.audio_service, "question_audio_url", lambda key: f"/assets/{key}")
        monkeypatch.setattr("app.services.module_service.random.sample", lambda seq, k: [seq[2], seq[0]])

        result = await service.get_random_questions(module_id=1, limit=2)
        assert [item.id for item in result] == [3, 1]

    @pytest.mark.asyncio
    async def test_get_random_questions_returns_all_when_limit_matches(self, monkeypatch):
        questions = [_question(1, audio_storage_key="a.mp3"), _question(2, audio_storage_key="b.mp3")]
        service = ModuleService(_db_with_scalars(questions))
        monkeypatch.setattr(service.audio_service, "has_question_audio", lambda _: True)
        monkeypatch.setattr(service.audio_service, "question_audio_url", lambda key: f"/assets/{key}")

        result = await service.get_random_questions(module_id=1, limit=2)
        assert [item.id for item in result] == [1, 2]

    @pytest.mark.asyncio
    async def test_count_questions_for_modules_returns_counts_per_module(self, monkeypatch):
        repo = SimpleNamespace(
            list_active_modules=AsyncMock(return_value=[]),
            list_questions_for_module=AsyncMock(return_value=[]),
            list_questions_for_modules=AsyncMock(
                return_value=[
                    _question(1, module_id=1, audio_storage_key="same.mp3", standard_responses=[_std("ok")]),
                    _question(2, module_id=1, audio_storage_key="same.mp3", standard_responses=[_std("ok"), _std("more")]),
                    _question(3, module_id=2, audio_storage_key="q3.mp3", standard_responses=[_std("ok")]),
                ]
            ),
            get_latest_evaluation_config=AsyncMock(return_value=None),
        )
        audio = SimpleNamespace(
            has_question_audio=lambda _: True,
            question_audio_url=lambda key: f"/assets/{key}",
        )
        service, _, _ = _service_with_repo(repo=repo, audio_service=audio)

        counts = await service.count_questions_for_modules([1, 2, 3])
        assert counts == {1: 1, 2: 1, 3: 0}

    @pytest.mark.asyncio
    async def test_get_active_evaluation_config_returns_latest(self):
        config = SimpleNamespace(id=10)
        repo = SimpleNamespace(
            list_active_modules=AsyncMock(return_value=[]),
            list_questions_for_module=AsyncMock(return_value=[]),
            list_questions_for_modules=AsyncMock(return_value=[]),
            get_latest_evaluation_config=AsyncMock(return_value=config),
        )
        service, _, _ = _service_with_repo(repo=repo)

        result = await service.get_active_evaluation_config(1)
        assert result is config

    @pytest.mark.asyncio
    async def test_get_active_evaluation_config_raises_when_missing(self):
        service, _, _ = _service_with_repo()
        with pytest.raises(HTTPException) as exc:
            await service.get_active_evaluation_config(1)
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_update_evaluation_config_updates_existing_record(self):
        existing = SimpleNamespace(
            prompt_template="old",
            apply_scoring_weights=AsyncMock(),
        )
        # make method sync behavior
        existing.apply_scoring_weights = lambda _: None
        repo = SimpleNamespace(
            list_active_modules=AsyncMock(return_value=[SimpleNamespace(id=1, slug="mod")]),
            list_questions_for_module=AsyncMock(return_value=[]),
            list_questions_for_modules=AsyncMock(return_value=[]),
            get_latest_evaluation_config=AsyncMock(return_value=existing),
        )
        service, db, _ = _service_with_repo(repo=repo)
        payload = SimpleNamespace(prompt_template="new-template", scoring_weights={"courtesy": 2.0})

        result = await service.update_evaluation_config("mod", payload)
        assert result is existing
        assert existing.prompt_template == "new-template"
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(existing)

    @pytest.mark.asyncio
    async def test_update_evaluation_config_creates_new_record_when_missing(self):
        repo = SimpleNamespace(
            list_active_modules=AsyncMock(return_value=[SimpleNamespace(id=5, slug="mod")]),
            list_questions_for_module=AsyncMock(return_value=[]),
            list_questions_for_modules=AsyncMock(return_value=[]),
            get_latest_evaluation_config=AsyncMock(return_value=None),
        )
        service, db, _ = _service_with_repo(repo=repo)
        payload = SimpleNamespace(
            prompt_template="template",
            scoring_weights={
                "courtesy": 2.0,
                "empathy": 1.0,
                "respect": 1.0,
                "tone": 1.0,
                "communication": 1.0,
            },
        )

        result = await service.update_evaluation_config("mod", payload)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(result)