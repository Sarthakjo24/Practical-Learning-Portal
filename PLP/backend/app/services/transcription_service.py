from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from app.core.config import settings


class TranscriptionService:
    _model: object | None = None

    def _get_model(self) -> object:
        if self.__class__._model is None:
            from faster_whisper import WhisperModel

            self.__class__._model = WhisperModel(
                settings.faster_whisper_model,
                device=settings.faster_whisper_device,
                compute_type=settings.faster_whisper_compute_type,
            )
        return self.__class__._model

    async def transcribe(self, storage_key: str) -> dict:
        audio_path = (settings.storage_dir / storage_key).resolve()
        if sys.platform == "win32":
            return await asyncio.to_thread(self._transcribe_openai, audio_path)
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_openai(self, audio_path: Path) -> dict:
        if not settings.openai_api_key or settings.openai_api_key == "sk-placeholder":
            raise RuntimeError(
                "Transcription is not supported on Windows with the local faster-whisper backend. "
                "Set OPENAI_API_KEY in backend/.env or run the worker on Linux/WSL."
            )

        import openai

        openai.api_key = settings.openai_api_key
        with open(audio_path, "rb") as audio_file:
            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        return {
            "transcript_text": response.get("text", ""),
            "detected_language": response.get("language", None),
            "model_name": "openai/whisper-1",
            "processing_seconds": 0.0,
        }

    def _transcribe_sync(self, audio_path: Path) -> dict:
        started = time.perf_counter()
        model = self._get_model()
        segments, info = model.transcribe(str(audio_path))
        transcript = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
        return {
            "transcript_text": transcript,
            "detected_language": getattr(info, "language", None),
            "model_name": settings.faster_whisper_model,
            "processing_seconds": round(time.perf_counter() - started, 3),
        }
