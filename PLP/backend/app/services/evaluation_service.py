from __future__ import annotations

import json
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.questions import EvaluationConfig, Module, Question
from app.utils.helpers import extract_json_object


class EvaluationService:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)

    async def evaluate_answer(
        self,
        module: Module,
        question: Question,
        transcript_text: str,
        evaluation_config: EvaluationConfig,
    ) -> dict:
        prompt = self._build_prompt(
            template=evaluation_config.prompt_template,
            module=module,
            question=question,
            transcript_text=transcript_text,
            scoring_weights=evaluation_config.scoring_weights,
        )
        response = await self.client.chat.completions.create(
            model=evaluation_config.model_name or settings.openai_model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict behavior-based customer service evaluator. Return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return extract_json_object(content)

    def load_default_prompt_template(self) -> str:
        path: Path = settings.default_prompt_template_path
        return path.read_text(encoding="utf-8")

    def _build_prompt(
        self,
        template: str,
        module: Module,
        question: Question,
        transcript_text: str,
        scoring_weights: dict,
    ) -> str:
        standard_responses = [
            response.response_text
            for response in question.standard_responses
            if response.is_active
        ]
        return (
            template.replace("{{MODULE_TITLE}}", module.title)
            .replace("{{QUESTION_TITLE}}", question.title)
            .replace("{{QUESTION_TRANSCRIPT}}", question.scenario_transcript)
            .replace("{{CANDIDATE_TRANSCRIPT}}", transcript_text)
            .replace(
                "{{STANDARD_RESPONSES_LIST}}",
                json.dumps(standard_responses, ensure_ascii=False, indent=2),
            )
            .replace(
                "{{SCORING_WEIGHTS_JSON}}",
                json.dumps(scoring_weights, ensure_ascii=False, indent=2),
            )
        )
