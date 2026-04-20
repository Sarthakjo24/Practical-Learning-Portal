import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.evaluation_service import EvaluationService


def _mock_completion(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _module(title="Customer Support Basics"):
    return SimpleNamespace(title=title)


def _question(title="Handle escalation", scenario="Upset customer", responses=None):
    responses = responses if responses is not None else [SimpleNamespace(response_text="Apologize", is_active=True)]
    return SimpleNamespace(title=title, scenario_transcript=scenario, standard_responses=responses)


def _config():
    return SimpleNamespace(
        prompt_template="{{MODULE_TITLE}}|{{QUESTION_TITLE}}|{{QUESTION_TRANSCRIPT}}|{{CANDIDATE_TRANSCRIPT}}|{{STANDARD_RESPONSES_LIST}}|{{SCORING_WEIGHTS_JSON}}",
        scoring_weights={"courtesy": 1, "empathy": 2, "respect": 3, "tone": 4, "communication": 5},
        model_name="gpt-test-model",
    )


class TestEvaluationNormalization:
    def test_coerce_numeric_handles_none_empty_invalid_and_large_values(self):
        service = EvaluationService()
        assert service._coerce_numeric(None) is None
        assert service._coerce_numeric("") is None
        assert service._coerce_numeric("not-a-number") is None
        assert service._coerce_numeric("12345678901234567890") == 12345678901234567890.0

    def test_coerce_numeric_parses_strings_and_embedded_number(self):
        service = EvaluationService()
        assert service._coerce_numeric("4") == 4.0
        assert service._coerce_numeric("score: 4.5 / 10") == 4.5
        assert service._coerce_numeric(3) == 3.0

    def test_coerce_list_points_handles_none_empty_and_truncation(self):
        service = EvaluationService()
        assert service._coerce_list_points(None) == []
        assert service._coerce_list_points("") == []
        assert service._coerce_list_points("one; two\nthree\nfour") == ["one", "two", "three"]
        assert service._coerce_list_points([" one ", "", None, "two", "three", "four"]) == ["one", "None", "two"]

    def test_normalize_evaluation_payload_maps_aliases_and_nested_scores(self):
        service = EvaluationService()
        payload = {
            "score": "8.5",
            "courtesy_score": "7",
            "respect_score": "6",
            "empathy_score": "5",
            "tone_score": "4",
            "communication_score": "3",
            "strengths": "Clear communication; Empathy\nOwnership",
            "weakness": "Could summarize next steps",
            "feedback": "Strong answer overall.",
        }
        normalized = service._normalize_evaluation_payload(payload)
        assert normalized["total_score"] == 8.5
        assert normalized["sentiment_breakdown"] == {
            "courtesy": 7.0,
            "respect": 6.0,
            "empathy": 5.0,
            "tone": 4.0,
            "sympathy": 5.0,
        }
        assert normalized["handling_breakdown"] == {
            "communication_clarity": 3.0,
            "engagement": 3.0,
            "problem_handling_approach": 3.0,
        }
        assert normalized["strengths"] == ["Clear communication", "Empathy", "Ownership"]
        assert normalized["improvement_areas"] == ["Could summarize next steps"]
        assert normalized["final_summary"] == "Strong answer overall."


class TestEvaluationPrompts:
    def test_build_prompt_includes_substituted_content_and_guidance(self):
        service = EvaluationService()
        prompt = service._build_prompt(
            template=_config().prompt_template,
            module=_module(),
            question=_question(),
            transcript_text="Candidate response",
            scoring_weights=_config().scoring_weights,
        )
        assert "Customer Support Basics" in prompt
        assert "Handle escalation" in prompt
        assert "Candidate response" in prompt
        assert "Apologize" in prompt
        assert "Output guidance" in prompt

    def test_build_overall_summary_prompt_contains_identity_and_answer_payload(self):
        service = EvaluationService()
        prompt = service._build_overall_summary_prompt(
            module_title="Module X",
            candidate_name="Jane Doe",
            candidate_id="CAND-123",
            evaluated_answers=[{"question_code": "Q-001", "score": 9}],
        )
        assert "MODULE TITLE" in prompt
        assert "Jane Doe" in prompt
        assert "Q-001" in prompt
        assert "Return strict JSON" in prompt


class TestEvaluationServiceCalls:
    @pytest.mark.asyncio
    async def test_evaluate_answer_returns_normalized_payload(self, evaluation_service):
        evaluation_service.client.chat.completions.create = AsyncMock(
            return_value=_mock_completion(
                json.dumps({"score": "9", "strengths": ["Empathy"], "weakness": "Summarize next steps"})
            )
        )
        result = await evaluation_service.evaluate_answer(_module(), _question(), "Candidate response", _config())
        assert result["total_score"] == 9.0
        assert result["strengths"] == ["Empathy"]
        assert result["improvement_areas"] == ["Summarize next steps"]

    @pytest.mark.asyncio
    async def test_evaluate_answer_retries_after_parse_error_then_succeeds(self, evaluation_service, monkeypatch):
        evaluation_service._sleep = AsyncMock()
        evaluation_service.client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_completion("not json"),
                _mock_completion(json.dumps({"total_score": 7, "strengths": ["Clear"], "improvement_areas": ["Empathy"]})),
            ]
        )
        result = await evaluation_service.evaluate_answer(_module(), _question(), "Candidate response", _config())
        assert result["total_score"] == 7.0
        assert result["improvement_areas"] == ["Empathy"]

    @pytest.mark.asyncio
    async def test_evaluate_answer_raises_after_retryable_errors(self, evaluation_service, monkeypatch):
        evaluation_service._sleep = AsyncMock()
        evaluation_service.client.chat.completions.create = AsyncMock(
            side_effect=TimeoutError("rate limited")
        )
        with pytest.raises(RuntimeError, match="OpenAI evaluation failed after"):
            await evaluation_service.evaluate_answer(_module(), _question(), "Candidate response", _config())

    @pytest.mark.asyncio
    async def test_evaluate_answer_raises_if_client_missing(self):
        service = EvaluationService()
        service.client = None
        with pytest.raises(RuntimeError, match="missing OPENAI_API_KEY"):
            await service.evaluate_answer(_module(), _question(), "Candidate response", _config())

    @pytest.mark.asyncio
    async def test_summarize_candidate_performance_returns_empty_dict_for_no_answers(self, evaluation_service):
        result = await evaluation_service.summarize_candidate_performance("Module", "Jane", "C-1", [])
        assert result == {}

    @pytest.mark.asyncio
    async def test_summarize_candidate_performance_retries_missing_summary_then_succeeds(
        self, evaluation_service, monkeypatch
    ):
        evaluation_service._sleep = AsyncMock()
        evaluation_service.client.chat.completions.create = AsyncMock(
            side_effect=[
                _mock_completion(json.dumps({"summary": "wrong key"})),
                _mock_completion(json.dumps({"overall_summary": "Improved across questions."})),
            ]
        )
        result = await evaluation_service.summarize_candidate_performance(
            "Module A",
            "Candidate A",
            "C-1",
            [{"question_code": "Q-1", "score": 7}],
        )
        assert result["overall_summary"] == "Improved across questions."

    @pytest.mark.asyncio
    async def test_summarize_candidate_performance_raises_after_malformed_payloads(self, evaluation_service, monkeypatch):
        evaluation_service._sleep = AsyncMock()
        evaluation_service.client.chat.completions.create = AsyncMock(
            side_effect=[_mock_completion("not json"), _mock_completion("still not json"), _mock_completion("{}")]
        )
        with pytest.raises(RuntimeError, match="summary generation failed after"):
            await evaluation_service.summarize_candidate_performance(
                "Module A",
                "Candidate A",
                "C-1",
                [{"question_code": "Q-1", "score": 7}],
            )