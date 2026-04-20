from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.audio_service import AudioService, LocalAudioStorage


class UploadStub:
    def __init__(self, filename, chunks):
        self.filename = filename
        self._chunks = list(chunks)
        self._idx = 0
        self.closed = False

    async def read(self, _size):
        if self._idx >= len(self._chunks):
            return b""
        chunk = self._chunks[self._idx]
        self._idx += 1
        return chunk

    async def close(self):
        self.closed = True


class TestAudioServiceUrlsAndStorage:
    def test_candidate_audio_url_returns_storage_path_or_none(self):
        service = AudioService(storage=LocalAudioStorage(Path("."), Path(".")))
        assert service.candidate_audio_url("candidate/session/file.webm") == "/storage/candidate/session/file.webm"
        assert service.candidate_audio_url(None) is None

    def test_has_question_audio_and_delete_storage_key(self, tmp_path):
        service = AudioService(storage=LocalAudioStorage(tmp_path, tmp_path / "qaudio"))
        (tmp_path / "qaudio").mkdir(parents=True, exist_ok=True)
        (tmp_path / "qaudio" / "q1.mp3").write_bytes(b"x")
        assert service.has_question_audio("q1.mp3") is True
        assert service.has_question_audio(None) is False

        file_path = tmp_path / "candidate_recordings/s1/q1.webm"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"abc")
        service.delete_storage_key("candidate_recordings/s1/q1.webm")
        assert not file_path.exists()

    def test_resolve_storage_key_rejects_path_traversal(self, tmp_path):
        service = AudioService(storage=LocalAudioStorage(tmp_path, tmp_path / "qaudio"))
        with pytest.raises(ValueError):
            service._resolve_storage_key("../escape.webm")


class TestAudioServiceQuestionAudioResolution:
    def test_normalize_audio_stem_reduces_case_spaces_and_separators(self):
        service = AudioService(storage=LocalAudioStorage(Path("."), Path(".")))
        assert service._normalize_audio_stem(" Module 1 - Question_2 ") == "module1question2"

    def test_resolve_question_audio_name_prefers_exact_then_normalized(self, tmp_path):
        service = AudioService(storage=LocalAudioStorage(tmp_path, tmp_path))
        (tmp_path / "Module 1 Question 4.wav").write_bytes(b"x")
        assert service._resolve_question_audio_name("module_1_question_4.wav") == "Module 1 Question 4.wav"

    def test_resolve_question_audio_name_returns_requested_when_no_match(self, tmp_path):
        service = AudioService(storage=LocalAudioStorage(tmp_path, tmp_path))
        assert service._resolve_question_audio_name("missing.wav") == "missing.wav"


class TestAudioServiceSaveCandidateRecording:
    @pytest.mark.asyncio
    async def test_save_candidate_recording_rejects_unsupported_extension(self, tmp_path):
        service = AudioService(
            storage=LocalAudioStorage(tmp_path, tmp_path / "qaudio"),
            allowed_extensions=[".webm"],
        )
        upload = UploadStub("answer.txt", [b"hello"])
        with pytest.raises(HTTPException) as exc:
            await service.save_candidate_recording(upload, "session-1", "question-1")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_save_candidate_recording_rejects_oversized_upload(self, tmp_path):
        service = AudioService(
            storage=LocalAudioStorage(tmp_path, tmp_path / "qaudio"),
            max_upload_bytes=4,
        )
        upload = UploadStub("answer.webm", [b"12345"])
        with pytest.raises(HTTPException) as exc:
            await service.save_candidate_recording(upload, "session-1", "question-1")
        assert exc.value.status_code == 413

    @pytest.mark.asyncio
    async def test_save_candidate_recording_persists_file_and_returns_storage_key(self, tmp_path):
        service = AudioService(
            storage=LocalAudioStorage(tmp_path, tmp_path / "qaudio"),
            max_upload_bytes=1024 * 1024,
        )
        upload = UploadStub("answer.webm", [b"hello", b" ", b"world"])

        storage_key = await service.save_candidate_recording(upload, "session-1", "question-1")
        saved_file = tmp_path / storage_key

        assert storage_key.endswith(".webm")
        assert saved_file.exists()
        assert saved_file.read_bytes() == b"hello world"
        assert upload.closed is True