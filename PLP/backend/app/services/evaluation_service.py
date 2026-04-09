from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

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

    async def summarize_candidate_performance(
        self,
        module_title: str,
        candidate_name: str,
        candidate_id: str,
        evaluated_answers: list[dict[str, Any]],
    ) -> str:
        if not evaluated_answers:
            return ""

        if self.client is None:
            raise RuntimeError("OpenAI summary unavailable (missing OPENAI_API_KEY).")

        prompt = self._build_overall_summary_prompt(
            module_title=module_title,
            candidate_name=candidate_name,
            candidate_id=candidate_id,
            evaluated_answers=evaluated_answers,
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.effective_openai_eval_model,
                    response_format={"type": "json_object"},
                    temperature=0,
                    messages=[
                        {
                            "role": "system",
                            "content": "You create concise and accurate candidate performance summaries. Return JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                content = response.choices[0].message.content or "{}"
                payload = extract_json_object(content)
                summary = str(payload.get("overall_summary") or "").strip()
                if not summary:
                    raise ValueError("Missing overall_summary in model output.")
                return summary
            except ValueError as exc:
                last_error = RuntimeError(f"Unable to parse summary result: {exc}")
                logger.warning(
                    "OpenAI returned non-JSON or incomplete summary payload (attempt %s/%s).",
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
            last_error = RuntimeError("Unknown OpenAI summary error.")
        raise RuntimeError(
            f"OpenAI summary generation failed after {self.max_retries} attempts: {last_error}"
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
        standard_responses_payload = (
            standard_responses
            if standard_responses
            else ["No standard responses configured for this question. Evaluate only using the scenario and transcript."]
        )
        base_prompt = (
            template.replace("{{MODULE_TITLE}}", module.title or "")
            .replace("{{QUESTION_TITLE}}", question.title or "")
            .replace("{{QUESTION_TRANSCRIPT}}", question.scenario_transcript or "")
            .replace("{{CANDIDATE_TRANSCRIPT}}", transcript_text or "")
            .replace(
                "{{STANDARD_RESPONSES_LIST}}",
                json.dumps(standard_responses_payload, ensure_ascii=False, indent=2),
            )
            .replace(
                "{{SCORING_WEIGHTS_JSON}}",
                json.dumps(scoring_weights, ensure_ascii=False, indent=2),
            )
        )
        enforcement_suffix = (
            "\n\nStrict output enforcement:\n"
            "- If reference standard responses are unavailable, use the scenario transcript and behavior rubric only.\n"
            "- `improvement_areas` must include at least one concrete, transcript-grounded weakness.\n"
            "- Do not return empty arrays for `strengths` or `improvement_areas`.\n"
            "- Avoid boilerplate weakness text; each weakness must point to a real gap in empathy, tone, respect, engagement, clarity, or handling approach.\n"
        )
        return f"{base_prompt}{enforcement_suffix}"

    def _build_overall_summary_prompt(
        self,
        module_title: str,
        candidate_name: str,
        candidate_id: str,
        evaluated_answers: list[dict[str, Any]],
    ) -> str:
        return (
            "You are evaluating overall behavior-based customer support performance across multiple responses.\n\n"
            f"MODULE TITLE:\n{module_title}\n\n"
            f"CANDIDATE NAME:\n{candidate_name}\n\n"
            f"CANDIDATE ID:\n{candidate_id}\n\n"
            "EVALUATED RESPONSES JSON:\n"
            f"{json.dumps(evaluated_answers, ensure_ascii=False, indent=2)}\n\n"
            "Instructions:\n"
            "- Create one combined performance summary across all responses.\n"
            "- Focus on patterns in empathy, respect, courtesy, tone, communication clarity, engagement, and handling approach.\n"
            "- Mention consistency across responses and highest-priority improvement themes.\n"
            "- Do not provide per-question summaries.\n"
            "- Do not mention tool availability, fallback behavior, or system errors.\n"
            "- Keep it clear and concise (90-140 words).\n\n"
            "Return strict JSON:\n"
            "{\n"
            '  "overall_summary": "string"\n'
            "}\n"
        )
