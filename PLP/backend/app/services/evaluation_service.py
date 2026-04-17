from __future__ import annotations

import asyncio
import json
import logging
import re
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
                            "content": "You are a fair and balanced behavior-based customer service evaluator. Be encouraging where warranted and constructive in feedback. Return JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                content = response.choices[0].message.content or "{}"
                payload = extract_json_object(content)
                return self._normalize_evaluation_payload(payload)
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
    ) -> dict[str, Any]:
        if not evaluated_answers:
            return {}

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
                            "content": "You create fair, balanced, and accurate candidate performance summaries. Be encouraging where warranted. Return JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                content = response.choices[0].message.content or "{}"
                payload = extract_json_object(content)
                summary = str(payload.get("overall_summary") or "").strip()
                if not summary:
                    raise ValueError("Missing overall_summary in model output.")
                return payload
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
        base_prompt = (
            template.replace("{{MODULE_TITLE}}", module.title or "")
            .replace("{{QUESTION_TITLE}}", question.title or "")
            .replace("{{QUESTION_TRANSCRIPT}}", question.scenario_transcript or "")
            .replace("{{QUESTION_TEXT}}", question.scenario_transcript or "")
            .replace("{{CANDIDATE_TRANSCRIPT}}", transcript_text or "")
            .replace("{{CANDIDATE_RESPONSE}}", transcript_text or "")
            .replace(
                "{{STANDARD_RESPONSES_LIST}}",
                json.dumps(standard_responses, ensure_ascii=False, indent=2),
            )
            .replace(
                "{{SCORING_WEIGHTS_JSON}}",
                json.dumps(scoring_weights, ensure_ascii=False, indent=2),
            )
        )
        enforcement_suffix = (
            "\n\nOutput guidance:\n"
            "- If reference standard responses are unavailable, use the scenario transcript and behavior rubric only.\n"
            "- Provide at least one item in both `strengths` and `improvement_areas`.\n"
            "- Keep feedback constructive and specific to the candidate's actual transcript.\n"
        )
        return f"{base_prompt}{enforcement_suffix}"

    def _normalize_evaluation_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})

        if normalized.get("total_score") is None and normalized.get("score") is not None:
            normalized["total_score"] = normalized.get("score")
        normalized["total_score"] = self._coerce_numeric(normalized.get("total_score"))

        sentiment = normalized.get("sentiment_breakdown")
        if not isinstance(sentiment, dict):
            sentiment = {}
        if sentiment.get("courtesy") is None and normalized.get("courtesy_score") is not None:
            sentiment["courtesy"] = normalized.get("courtesy_score")
        if sentiment.get("respect") is None and normalized.get("respect_score") is not None:
            sentiment["respect"] = normalized.get("respect_score")
        if sentiment.get("empathy") is None and normalized.get("empathy_score") is not None:
            sentiment["empathy"] = normalized.get("empathy_score")
        if sentiment.get("tone") is None and normalized.get("tone_score") is not None:
            sentiment["tone"] = normalized.get("tone_score")
        sentiment["courtesy"] = self._coerce_numeric(sentiment.get("courtesy"))
        sentiment["respect"] = self._coerce_numeric(sentiment.get("respect"))
        sentiment["empathy"] = self._coerce_numeric(sentiment.get("empathy"))
        sentiment["tone"] = self._coerce_numeric(sentiment.get("tone"))
        if sentiment.get("sympathy") is None:
            sentiment["sympathy"] = sentiment.get("empathy")
        sentiment["sympathy"] = self._coerce_numeric(sentiment.get("sympathy"))
        normalized["sentiment_breakdown"] = sentiment

        handling = normalized.get("handling_breakdown")
        if not isinstance(handling, dict):
            handling = {}
        communication_score = normalized.get("communication_score")
        if handling.get("communication_clarity") is None and communication_score is not None:
            handling["communication_clarity"] = communication_score
        if handling.get("engagement") is None and communication_score is not None:
            handling["engagement"] = communication_score
        if handling.get("problem_handling_approach") is None and communication_score is not None:
            handling["problem_handling_approach"] = communication_score
        handling["communication_clarity"] = self._coerce_numeric(handling.get("communication_clarity"))
        handling["engagement"] = self._coerce_numeric(handling.get("engagement"))
        handling["problem_handling_approach"] = self._coerce_numeric(handling.get("problem_handling_approach"))
        normalized["handling_breakdown"] = handling

        normalized["strengths"] = self._coerce_list_points(normalized.get("strengths"))

        if normalized.get("improvement_areas") is None and normalized.get("weakness") is not None:
            normalized["improvement_areas"] = normalized.get("weakness")
        normalized["improvement_areas"] = self._coerce_list_points(normalized.get("improvement_areas"))

        if not str(normalized.get("final_summary") or "").strip():
            normalized["final_summary"] = str(normalized.get("feedback") or "").strip()

        return normalized

    def _coerce_list_points(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()][:3]

        text = str(value or "").strip()
        if not text:
            return []

        parts = [
            re.sub(r"^[\-\*\d\.\)\s]+", "", segment).strip()
            for segment in re.split(r"[\n;]+", text)
            if segment.strip()
        ]
        cleaned = [item for item in parts if item]
        if cleaned:
            return cleaned[:3]

        return [text][:1]

    def _coerce_numeric(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)

        raw = str(value).strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            match = re.search(r"-?\d+(?:\.\d+)?", raw)
            if not match:
                return None
            try:
                return float(match.group(0))
            except ValueError:
                return None

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
            "- Provide a holistic, fair evaluation of the candidate across all responses.\n"
            "- `total_score`: An overall score (0-10) reflecting the candidate's aggregate performance across all questions. Be fair — give credit for genuine effort, empathy, and willingness to help.\n"
            "- `strengths`: A list of 2-4 key recurring strengths observed across the responses.\n"
            "- `weaknesses`: A list of 1-3 constructive areas for improvement. Be specific and helpful, not harsh.\n"
            "- `question_wise_scores`: An array with one entry per evaluated question containing `question_code`, `question_title`, and `score` (0-10).\n"
            "- `overall_summary`: A combined performance narrative (90-150 words) focusing on patterns in empathy, respect, courtesy, tone, communication clarity, engagement, and handling approach. Mention consistency across responses and highlight priority improvement themes.\n"
            "- Do not provide full per-question summaries inside the overall_summary text.\n"
            "- Do not mention tool availability, fallback behavior, or system errors.\n\n"
            "Return strict JSON:\n"
            "{\n"
            '  "total_score": 0,\n'
            '  "strengths": ["string"],\n'
            '  "weaknesses": ["string"],\n'
            '  "question_wise_scores": [{"question_code": "string", "question_title": "string", "score": 0}],\n'
            '  "overall_summary": "string"\n'
            "}\n"
        )
