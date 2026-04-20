from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import subprocess

from app.services.transcription_service import TranscriptionService


class TestTranscriptionHelpers:
    def test_normalize_transcript_text_collapses_whitespace_and_control_characters(self):
        assert TranscriptionService._normalize_transcript_text("  hello \n world \t \u0000 ") == "hello world"
        assert TranscriptionService._normalize_transcript_text(None) == ""

    def test_is_latin_script_text_detects_latin_and_rejects_non_latin(self):
        assert TranscriptionService._is_latin_script_text("This is English.") is True
        assert TranscriptionService._is_latin_script_text("नमस्ते") is False
        assert TranscriptionService._is_latin_script_text("12345 ???") is False


class TestTranscriptionPostprocess:
    @pytest.mark.asyncio
    async def test_postprocess_payload_normalizes_text_when_supported(self):
        service = TranscriptionService()
        service._openai_client = None
        payload = {"transcript_text": "  hello \n world ", "detected_language": "en"}
        result = await service._postprocess_payload(payload, Path("dummy.wav"), source="openai")
        assert result["transcript_text"] == "hello world"

    @pytest.mark.asyncio
    async def test_postprocess_payload_clears_transcript_for_unsupported_language(self):
        service = TranscriptionService()
        service._openai_client = None
        payload = {"transcript_text": "bonjour", "detected_language": "fr"}
        result = await service._postprocess_payload(payload, Path("dummy.wav"), source="openai")
        assert result["transcript_text"] == ""

    @pytest.mark.asyncio
    async def test_postprocess_payload_uses_openai_fallback_when_faster_whisper_empty(self):
        service = TranscriptionService()
        service._openai_client = object()
        service._transcribe_openai = AsyncMock(
            return_value={"transcript_text": "Recovered", "detected_language": "en"}
        )
        result = await service._postprocess_payload(
            {"transcript_text": "", "detected_language": "en"}, Path("dummy.wav"), source="faster_whisper"
        )
        assert result["transcript_text"] == "Recovered"

    @pytest.mark.asyncio
    async def test_postprocess_payload_fallback_failure_then_clears_unsupported_text(self):
        service = TranscriptionService()
        service._openai_client = object()
        service._transcribe_openai = AsyncMock(side_effect=RuntimeError("fallback failed"))
        result = await service._postprocess_payload(
            {"transcript_text": "bonjour", "detected_language": "fr"}, Path("dummy.wav"), source="faster_whisper"
        )
        assert result["transcript_text"] == ""


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_transcribe_raises_when_audio_file_missing(self, tmp_path):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=False)
        with pytest.raises(FileNotFoundError):
            await service.transcribe("missing.wav")

    @pytest.mark.asyncio
    async def test_transcribe_uses_faster_whisper_success_path(self, tmp_path):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")

        service._transcribe_subprocess = Mock(return_value={"transcript_text": "FW text", "detected_language": "en"})
        service._postprocess_payload = AsyncMock(return_value={"transcript_text": "FW text", "detected_language": "en"})
        service._transcribe_openai = AsyncMock()

        result = await service.transcribe("audio.wav")
        assert result["transcript_text"] == "FW text"
        service._transcribe_subprocess.assert_called_once()
        service._transcribe_openai.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_transcribe_uses_injected_subprocess_runner(self, tmp_path):
        runner = Mock(return_value={"transcript_text": "runner text", "detected_language": "en"})
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True, subprocess_runner=runner)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        service._postprocess_payload = AsyncMock(return_value={"transcript_text": "runner text", "detected_language": "en"})

        result = await service.transcribe("audio.wav")
        assert result["transcript_text"] == "runner text"
        runner.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_falls_back_to_openai_when_faster_whisper_fails(self, tmp_path):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")

        service._transcribe_subprocess = Mock(side_effect=RuntimeError("fw failed"))
        service._transcribe_openai = AsyncMock(return_value={"transcript_text": "OpenAI text", "detected_language": "en"})
        service._postprocess_payload = AsyncMock(return_value={"transcript_text": "OpenAI text", "detected_language": "en"})

        result = await service.transcribe("audio.wav")
        assert result["transcript_text"] == "OpenAI text"
        service._transcribe_openai.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transcribe_raises_runtime_error_when_no_backend_configured(self, tmp_path):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=False)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        service._openai_client = None

        with pytest.raises(RuntimeError, match="No transcription backend configured"):
            await service.transcribe("audio.wav")

    @pytest.mark.asyncio
    async def test_transcribe_raises_when_both_backends_fail(self, tmp_path):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        service._openai_client = SimpleNamespace()

        service._transcribe_subprocess = Mock(side_effect=RuntimeError("fw failed"))
        service._transcribe_openai = AsyncMock(side_effect=RuntimeError("openai failed"))

        with pytest.raises(RuntimeError, match="fallback also failed"):
            await service.transcribe("audio.wav")

    @pytest.mark.asyncio
    async def test_transcribe_reraises_faster_whisper_error_when_no_openai_client(self, tmp_path):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        service._openai_client = None
        service._transcribe_subprocess = Mock(side_effect=RuntimeError("fw failed hard"))

        with pytest.raises(RuntimeError, match="fw failed hard"):
            await service.transcribe("audio.wav")

    @pytest.mark.asyncio
    async def test_transcribe_uses_openai_only_mode(self, tmp_path):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=False)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        service._openai_client = SimpleNamespace()
        service._transcribe_openai = AsyncMock(return_value={"transcript_text": "ok", "detected_language": "en"})
        service._postprocess_payload = AsyncMock(return_value={"transcript_text": "ok", "detected_language": "en"})

        result = await service.transcribe("audio.wav")
        assert result["transcript_text"] == "ok"


class TestTranscribeOpenAIAndSubprocess:
    @pytest.mark.asyncio
    async def test_transcribe_openai_raises_without_client(self, tmp_path):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=False)
        service._openai_client = None
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
            await service._transcribe_openai(audio_file)

    @pytest.mark.asyncio
    async def test_transcribe_openai_returns_payload_shape(self, tmp_path):
        create_mock = AsyncMock(return_value=SimpleNamespace(text=" hello ", language="en"))
        openai_client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create_mock)))
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=False, openai_client=openai_client)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")

        payload = await service._transcribe_openai(audio_file)
        assert payload["transcript_text"] == "hello"
        assert payload["detected_language"] == "en"
        assert payload["model_name"]

    def test_transcribe_subprocess_raises_timeout(self, tmp_path, monkeypatch):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        monkeypatch.setattr(
            "app.services.transcription_service.subprocess.run",
            Mock(side_effect=subprocess.TimeoutExpired(cmd="x", timeout=300)),
        )

        with pytest.raises(RuntimeError, match="timed out"):
            service._transcribe_subprocess(audio_file)

    def test_transcribe_subprocess_raises_on_non_zero_exit(self, tmp_path, monkeypatch):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        monkeypatch.setattr(
            "app.services.transcription_service.subprocess.run",
            Mock(return_value=SimpleNamespace(returncode=2, stderr="boom", stdout="context")),
        )

        with pytest.raises(RuntimeError, match="exited with code 2"):
            service._transcribe_subprocess(audio_file)

    def test_transcribe_subprocess_uses_non_windows_settings(self, tmp_path, monkeypatch):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        monkeypatch.setattr("app.services.transcription_service.sys.platform", "linux")
        monkeypatch.setattr(
            "app.services.transcription_service.subprocess.run",
            Mock(
                return_value=SimpleNamespace(
                    returncode=0,
                    stderr="",
                    stdout='{"transcript_text":"ok","detected_language":"en"}',
                )
            ),
        )

        payload = service._transcribe_subprocess(audio_file)
        assert payload["transcript_text"] == "ok"

    def test_transcribe_subprocess_raises_when_output_missing(self, tmp_path, monkeypatch):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        monkeypatch.setattr(
            "app.services.transcription_service.subprocess.run",
            Mock(return_value=SimpleNamespace(returncode=0, stderr="", stdout="")),
        )

        with pytest.raises(RuntimeError, match="produced no output"):
            service._transcribe_subprocess(audio_file)

    def test_transcribe_subprocess_returns_json_payload_on_success(self, tmp_path, monkeypatch):
        service = TranscriptionService(storage_dir=tmp_path, use_faster_whisper=True)
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"x")
        monkeypatch.setattr(
            "app.services.transcription_service.subprocess.run",
            Mock(
                return_value=SimpleNamespace(
                    returncode=0,
                    stderr="",
                    stdout='{"transcript_text":"hello","detected_language":"en"}',
                )
            ),
        )

        payload = service._transcribe_subprocess(audio_file)
        assert payload["transcript_text"] == "hello"