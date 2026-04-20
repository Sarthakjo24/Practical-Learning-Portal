import json

import pytest

from app.services.scoring_service import ScoringService
from app.utils.helpers import (
    basename_from_path,
    deserialize_text_list,
    extract_json_object,
    sanitize_filename,
    serialize_text_list,
    slugify_text,
    trim_text,
)


class TestHelperUtilities:
    def test_sanitize_filename_replaces_unsafe_characters_and_falls_back(self):
        assert sanitize_filename("Quarterly Report 2024?.pdf") == "Quarterly-Report-2024-.pdf"
        assert sanitize_filename("  @@  ") == "audio"

    def test_slugify_text_normalizes_case_spacing_symbols_and_fallback(self):
        assert slugify_text("  Hello, World! Customer Support  ") == "hello-world-customer-support"
        assert slugify_text("") == "module"
        assert slugify_text(None) == "module"

    def test_trim_text_collapses_whitespace_and_uses_fallback(self):
        assert trim_text(None, "fallback") == "fallback"
        assert trim_text("  hello \n world  ", "fallback") == "hello world"
        assert trim_text("   ", "fallback") == "fallback"

    def test_basename_from_path_returns_leaf_name(self):
        assert basename_from_path(r"folder/subfolder/file-name.wav") == "file-name.wav"
        assert basename_from_path(r"folder\subfolder\file-name.wav") == "file-name.wav"
        assert basename_from_path(None) == ""

    def test_serialize_text_list_handles_none_string_and_list_values(self):
        assert serialize_text_list(None) == "[]"
        assert serialize_text_list("   ") == "[]"
        assert serialize_text_list("already-string") == "already-string"
        assert json.loads(serialize_text_list([" one ", "", None, "two "])) == ["one", "None", "two"]

    def test_deserialize_text_list_handles_json_list_string_and_bullets(self):
        assert deserialize_text_list(None) == []
        assert deserialize_text_list("") == []
        assert deserialize_text_list('["one", " two ", "", null]') == ["one", "two", "None"]
        assert deserialize_text_list('"single"') == ["single"]
        assert deserialize_text_list("- first\n- second") == ["first", "second"]

    def test_extract_json_object_parses_direct_and_wrapped_json(self):
        assert extract_json_object('{"score": 9, "notes": ["clear"]}') == {"score": 9, "notes": ["clear"]}
        wrapped = 'Result:\n{"score": 7, "status": "ok"}\nThanks'
        assert extract_json_object(wrapped) == {"score": 7, "status": "ok"}

    def test_extract_json_object_raises_for_malformed_or_missing_json(self):
        with pytest.raises(ValueError):
            extract_json_object("no json here")
        with pytest.raises(ValueError):
            extract_json_object('{"score": 7')


class TestScoringService:
    def test_aggregate_session_score_returns_none_for_empty_scores(self):
        assert ScoringService.aggregate_session_score([]) is None

    def test_aggregate_session_score_averages_and_rounds(self):
        assert ScoringService.aggregate_session_score([7, 8.5, 9]) == 8.17

    def test_aggregate_session_score_handles_extremely_large_numbers(self):
        result = ScoringService.aggregate_session_score([1e18, 1e18, 1e18 + 1])
        assert result == 1e18