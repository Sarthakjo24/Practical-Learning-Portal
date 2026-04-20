from __future__ import annotations

import re
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.utils.helpers import basename_from_path, sanitize_filename


class LocalAudioStorage:
    def __init__(self, storage_dir: Path, question_audio_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.question_audio_dir = question_audio_dir

    def resolve_storage_key(self, storage_key: str) -> Path:
        candidate = (self.storage_dir / storage_key).resolve()
        storage_root = self.storage_dir.resolve()
        if not str(candidate).startswith(str(storage_root)):
            raise ValueError("Refusing to access storage path outside configured storage root.")
        return candidate

    def question_audio_exists(self, file_name: str) -> bool:
        return (self.question_audio_dir / file_name).exists()

    def list_question_audio_files(self) -> list[Path]:
        return [path for path in self.question_audio_dir.iterdir() if path.is_file()]


class AudioService:
    def __init__(
        self,
        *,
        storage: LocalAudioStorage | None = None,
        allowed_extensions: list[str] | None = None,
        max_upload_bytes: int | None = None,
    ) -> None:
        settings.ensure_directories()
        self.storage = storage or LocalAudioStorage(settings.storage_dir, settings.question_audio_dir)
        self.allowed_extensions = allowed_extensions or list(settings.allowed_audio_extensions)
        self.max_upload_bytes = max_upload_bytes if max_upload_bytes is not None else settings.max_audio_upload_bytes

    async def save_candidate_recording(self, upload: UploadFile, session_id: str, question_id: str) -> str:
        extension = Path(upload.filename or "recording.webm").suffix.lower()
        if extension not in self.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format. Allowed: {', '.join(self.allowed_extensions)}",
            )

        file_name = f"{sanitize_filename(question_id)}{extension}"
        storage_key = f"candidate_recordings/{session_id}/{file_name}"
        destination = self._resolve_storage_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        total_size = 0
        async with aiofiles.open(destination, "wb") as out_file:
            while chunk := await upload.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > self.max_upload_bytes:
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
        return self.storage.question_audio_exists(resolved_name)

    def delete_storage_key(self, storage_key: str | None) -> None:
        if not storage_key:
            return
        path = self._resolve_storage_key(storage_key)
        if path.exists():
            path.unlink()

    def _resolve_storage_key(self, storage_key: str) -> Path:
        return self.storage.resolve_storage_key(storage_key)

    def _resolve_question_audio_name(self, storage_key: str) -> str:
        requested_name = basename_from_path(storage_key)
        if self.storage.question_audio_exists(requested_name):
            return requested_name

        requested_path = Path(requested_name)
        requested_suffix = requested_path.suffix.lower()
        requested_stem = self._normalize_audio_stem(requested_path.stem)

        for candidate in self.storage.list_question_audio_files():
            if candidate.suffix.lower() != requested_suffix:
                continue
            if self._normalize_audio_stem(candidate.stem) == requested_stem:
                return candidate.name

        return requested_name

    def _normalize_audio_stem(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())
