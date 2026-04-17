from __future__ import annotations

import random

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.questions import EvaluationConfig, Module, Question, StandardResponse
from app.schemas.evaluation import EvaluationConfigUpdate
from app.services.audio_service import AudioService
from app.utils.helpers import basename_from_path


class ModuleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audio_service = AudioService()

    async def list_active_modules(self) -> list[Module]:
        result = await self.db.execute(select(Module).where(Module.is_active.is_(True)).order_by(Module.title))
        return list(result.scalars().all())

    async def count_questions(self, module_id: int) -> int:
        result = await self.db.execute(
            select(Question)
            .where(Question.module_id == module_id)
            .options(selectinload(Question.standard_responses))
        )
        questions = list(result.scalars().all())
        eligible_questions = [question for question in questions if self._is_eligible_question(question)]
        return len(self._dedupe_questions_by_audio(eligible_questions))

    async def count_questions_for_modules(self, module_ids: list[int]) -> dict[int, int]:
        if not module_ids:
            return {}

        counts: dict[int, int] = {int(module_id): 0 for module_id in module_ids}
        result = await self.db.execute(
            select(Question)
            .where(Question.module_id.in_(module_ids))
            .options(selectinload(Question.standard_responses))
        )
        module_questions: dict[int, list[Question]] = {}
        for question in result.scalars().all():
            module_questions.setdefault(int(question.module_id), []).append(question)

        for module_id, questions in module_questions.items():
            eligible_questions = [question for question in questions if self._is_eligible_question(question)]
            deduped_questions = self._dedupe_questions_by_audio(eligible_questions)
            counts[int(module_id)] = len(deduped_questions)
        return counts

    async def get_module_by_slug(self, module_slug: str) -> Module:
        modules = await self.list_active_modules()
        for module in modules:
            if module.slug == module_slug:
                return module
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")

    async def get_random_questions(self, module_id: int, limit: int) -> list[Question]:
        result = await self.db.execute(
            select(Question)
            .where(Question.module_id == module_id)
            .options(selectinload(Question.standard_responses))
        )
        questions = list(result.scalars().all())
        eligible_questions = [
            question
            for question in questions
            if self._is_eligible_question(question)
        ]
        eligible_questions = self._dedupe_questions_by_audio(eligible_questions)

        if len(eligible_questions) < limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Module has only {len(eligible_questions)} eligible questions (with audio + standard responses), "
                    f"but {limit} are required for a session."
                ),
            )
        if len(eligible_questions) == limit:
            return eligible_questions
        return random.sample(eligible_questions, k=limit)

    async def get_active_evaluation_config(self, module_id: int) -> EvaluationConfig:
        result = await self.db.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.module_id == module_id)
            .order_by(EvaluationConfig.id.desc())
        )
        config = result.scalars().first()
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No evaluation configuration found for module.",
            )
        return config

    async def update_evaluation_config(self, module_slug: str, payload: EvaluationConfigUpdate) -> EvaluationConfig:
        module = await self.get_module_by_slug(module_slug)
        result = await self.db.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.module_id == module.id)
            .order_by(EvaluationConfig.id.desc())
        )
        config = result.scalars().first()

        if config is None:
            config = EvaluationConfig(module_id=module.id, prompt_template=payload.prompt_template)
            self.db.add(config)

        config.prompt_template = payload.prompt_template
        config.apply_scoring_weights(payload.scoring_weights)

        await self.db.commit()
        await self.db.refresh(config)
        return config

    def _is_eligible_question(self, question: Question) -> bool:
        if not self.audio_service.has_question_audio(question.audio_storage_key):
            return False
        return self._has_current_standard_response(question.standard_responses)

    def _has_current_standard_response(self, responses: list[StandardResponse] | None) -> bool:
        return self._active_standard_response_count(responses) > 0

    def _active_standard_response_count(self, responses: list[StandardResponse] | None) -> int:
        if not responses:
            return 0
        count = 0
        for response in responses:
            text = str(getattr(response, "response_text", "") or "").strip()
            if not text:
                continue
            if getattr(response, "is_active", True):
                count += 1
        return count

    def _dedupe_questions_by_audio(self, questions: list[Question]) -> list[Question]:
        deduped: dict[str, Question] = {}
        for question in questions:
            resolved_audio_url = self.audio_service.question_audio_url(question.audio_storage_key)
            audio_key = basename_from_path(resolved_audio_url).strip().lower()
            existing = deduped.get(audio_key)
            if existing is None:
                deduped[audio_key] = question
                continue

            if self._question_priority(question) > self._question_priority(existing):
                deduped[audio_key] = question

        return sorted(deduped.values(), key=lambda item: int(item.id))

    def _question_priority(self, question: Question) -> tuple[int, int, int]:
        std_count = self._active_standard_response_count(question.standard_responses)
        audio_key = str(question.audio_storage_key or "")
        has_explicit_path = 1 if ("/" in audio_key or "\\" in audio_key) else 0
        transcript_length = len(str(question.scenario_transcript or "").strip())
        return (std_count, has_explicit_path, transcript_length)
