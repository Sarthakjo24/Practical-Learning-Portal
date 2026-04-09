from __future__ import annotations

from pathlib import Path
import re

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.utils.helpers import basename_from_path, sanitize_filename


class AudioService:
    def __init__(self) -> None:
        settings.ensure_directories()

    async def save_candidate_recording(self, upload: UploadFile, session_id: str, question_id: str) -> str:
        extension = Path(upload.filename or "recording.webm").suffix.lower()
        if extension not in settings.allowed_audio_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format. Allowed: {', '.join(settings.allowed_audio_extensions)}",
            )

        file_name = f"{sanitize_filename(question_id)}{extension}"
        storage_key = f"candidate_recordings/{session_id}/{file_name}"
        destination = self._resolve_storage_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        total_size = 0
        async with aiofiles.open(destination, "wb") as out_file:
            while chunk := await upload.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > settings.max_audio_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Uploaded audio exceeds the configured size limit.",
                    )
                await out_file.write(chunk)

        await upload.close()
        return storage_key

    def candidate_audio_url(self, storage_key: str | None) -> str | None:
        if not storage_key:
            return None
        return f"/storage/{storage_key}"

    def question_audio_url(self, storage_key: str) -> str:
        return f"/assets/questions/{self._resolve_question_audio_name(storage_key)}"

    def has_question_audio(self, storage_key: str | None) -> bool:
        if not storage_key:
            return False
        resolved_name = self._resolve_question_audio_name(storage_key)
        return (settings.question_audio_dir / resolved_name).exists()

    def delete_storage_key(self, storage_key: str | None) -> None:
        if not storage_key:
            return
        path = self._resolve_storage_key(storage_key)
        if path.exists():
            path.unlink()

    def _resolve_storage_key(self, storage_key: str) -> Path:
        candidate = (settings.storage_dir / storage_key).resolve()
        storage_root = settings.storage_dir.resolve()
        if not str(candidate).startswith(str(storage_root)):
            raise ValueError("Refusing to access storage path outside configured storage root.")
        return candidate

    def _resolve_question_audio_name(self, storage_key: str) -> str:
        requested_name = basename_from_path(storage_key)
        question_audio_dir = settings.question_audio_dir
        exact_path = question_audio_dir / requested_name
        if exact_path.exists():
            return requested_name

        requested_path = Path(requested_name)
        requested_suffix = requested_path.suffix.lower()
        requested_stem = self._normalize_audio_stem(requested_path.stem)

        for candidate in question_audio_dir.iterdir():
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() != requested_suffix:
                continue
            if self._normalize_audio_stem(candidate.stem) == requested_stem:
                return candidate.name

        return requested_name

    def _normalize_audio_stem(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())
