from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.models.questions import EvaluationConfig, Module, Question
from app.utils.helpers import extract_json_object

logger = logging.getLogger(__name__)
_RETRYABLE_EVAL_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    APIError,
    TimeoutError,
    ConnectionError,
    OSError,
)


class EvaluationService:
    def __init__(self) -> None:
        self.client: AsyncOpenAI | None = None
        if settings.openai_api_key and settings.openai_api_key != "sk-placeholder":
            self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
        self.max_retries = 3

    async def evaluate_answer(
        self,
        module: Module,
        question: Question,
        transcript_text: str,
        evaluation_config: EvaluationConfig,
    ) -> dict:
        if self.client is None:
            raise RuntimeError("OpenAI evaluation unavailable (missing OPENAI_API_KEY).")

        prompt = self._build_prompt(
            template=evaluation_config.prompt_template,
            module=module,
            question=question,
            transcript_text=transcript_text,
            scoring_weights=evaluation_config.scoring_weights,
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=evaluation_config.model_name or settings.effective_openai_eval_model,
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
            except ValueError as exc:
                last_error = RuntimeError(f"Unable to parse evaluation result: {exc}")
                logger.warning(
                    "OpenAI returned non-JSON evaluation payload (attempt %s/%s).",
                    attempt + 1,
                    self.max_retries,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue
            except _RETRYABLE_EVAL_ERRORS as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
            except Exception as exc:
                last_error = exc
                break

        if last_error is None:
            last_error = RuntimeError("Unknown OpenAI evaluation error.")
        raise RuntimeError(
            f"OpenAI evaluation failed after {self.max_retries} attempts: {last_error}"
        )

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
            template.replace("{{MODULE_TITLE}}", module.title or "")
            .replace("{{QUESTION_TITLE}}", question.title or "")
            .replace("{{QUESTION_TRANSCRIPT}}", question.scenario_transcript or "")
            .replace("{{CANDIDATE_TRANSCRIPT}}", transcript_text or "")
            .replace(
                "{{STANDARD_RESPONSES_LIST}}",
                json.dumps(standard_responses, ensure_ascii=False, indent=2),
            )
            .replace(
                "{{SCORING_WEIGHTS_JSON}}",
                json.dumps(scoring_weights, ensure_ascii=False, indent=2),
            )
        )
