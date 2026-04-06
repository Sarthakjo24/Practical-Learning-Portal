from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.questions import EvaluationConfig, Module, Question, StandardResponse

DEFAULT_MODULE_TITLE = "Customer handling assessment"
DEFAULT_MODULE_DESCRIPTION = "Live customer handling scenarios for empathy, respect, and engagement evaluation."

DEFAULT_QUESTIONS = [
    {
        "file_name": "Citrix password.mp3",
        "scenario_transcript": (
            "A customer can't access Citrix because of a password problem and wants quick help without technical jargon."
        ),
    },
    {
        "file_name": "I am logged out of my PC.mp3",
        "scenario_transcript": (
            "The customer reports being unexpectedly logged out of their PC and needs reassurance and a clear next step."
        ),
    },
    {
        "file_name": "My computer shut down 6 times.mp3",
        "scenario_transcript": (
            "The customer says their computer has shut down repeatedly and is anxious about losing work."
        ),
    },
    {
        "file_name": "Not able to print the mail..mp3",
        "scenario_transcript": (
            "The customer cannot print an important email and needs calm guidance without complicated technical steps."
        ),
    },
    {
        "file_name": "Not able to send mails.mp3",
        "scenario_transcript": (
            "The customer is unable to send emails and wants a polite, empathetic response that focuses on the customer experience."
        ),
    },
]

DEFAULT_STANDARD_RESPONSES = [
    "I understand how frustrating this must be, and I appreciate you bringing it to my attention. I will help you resolve this smoothly.",
    "I would apologize for the inconvenience, ask a few simple clarifying questions, and reassure the customer that I am committed to resolving the issue.",
    "I would avoid technical jargon, stay calm and respectful, and explain the next steps clearly so the customer feels heard and supported.",
    "I would focus on empathy, respect, and engagement while ensuring the customer understands that we are taking ownership of the situation.",
]


def _get_question_audio_files() -> set[str]:
    root = settings.question_audio_dir
    if not root.exists():
        return set()
    return {item.name for item in root.iterdir() if item.is_file()}


def _build_standard_responses(question: Question) -> list[StandardResponse]:
    return [StandardResponse(question_id=question.id, response_text=text) for text in DEFAULT_STANDARD_RESPONSES]


async def seed_default_data() -> None:
    settings.ensure_directories()
    available_audio_files = _get_question_audio_files()
    if not available_audio_files:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Module).limit(1))
        module = result.scalars().first()

        if module is None:
            module = Module(
                title=DEFAULT_MODULE_TITLE,
                question_count=min(len(DEFAULT_QUESTIONS), settings.candidate_question_count),
                is_active=True,
            )
            session.add(module)
            await session.flush()

        config_result = await session.execute(select(EvaluationConfig).where(EvaluationConfig.module_id == module.id))
        if config_result.scalars().first() is None:
            prompt_template = Path(settings.default_prompt_template_path)
            default_template = prompt_template.read_text(encoding="utf-8") if prompt_template.exists() else ""
            session.add(
                EvaluationConfig(
                    module_id=module.id,
                    prompt_template=default_template,
                    weight_courtesy=1.5,
                    weight_empathy=1.5,
                    weight_respect=1.2,
                    weight_tone=1.0,
                    weight_communication=1.3,
                )
            )

        existing_question_rows = await session.execute(select(Question).where(Question.module_id == module.id))
        existing_questions = existing_question_rows.scalars().all()
        existing_audio_keys = {question.audio_storage_key for question in existing_questions}
        next_id = max((question.id for question in existing_questions if question.id is not None), default=0) + 1

        for question_definition in DEFAULT_QUESTIONS:
            file_name = question_definition["file_name"]
            if file_name not in available_audio_files:
                continue
            if file_name in existing_audio_keys:
                continue

            question = Question(
                id=next_id,
                module_id=module.id,
                scenario_transcript=question_definition["scenario_transcript"],
                audio_storage_key=file_name,
            )
            session.add(question)
            await session.flush()
            session.add_all(_build_standard_responses(question))
            next_id += 1

        await session.commit()
