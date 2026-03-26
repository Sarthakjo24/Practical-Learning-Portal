from __future__ import annotations

import asyncio
import time
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.config import settings


class TranscriptionService:
    _model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self.__class__._model is None:
            self.__class__._model = WhisperModel(
                settings.faster_whisper_model,
                device=settings.faster_whisper_device,
                compute_type=settings.faster_whisper_compute_type,
            )
        return self.__class__._model

    async def transcribe(self, storage_key: str) -> dict:
        audio_path = (settings.storage_dir / storage_key).resolve()
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

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
