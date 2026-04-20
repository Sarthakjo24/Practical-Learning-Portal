from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Callable

from openai import AsyncOpenAI

from app.core.config import settings

# Path to the isolated worker script
_WORKER_SCRIPT = Path(__file__).parent.parent / "utils" / "whisper_transcribe.py"
_ALLOWED_LANGUAGE_CODES = {"en", "hi"}


class TranscriptionService:
    def __init__(
        self,
        *,
        openai_client: AsyncOpenAI | None = None,
        storage_dir: Path | None = None,
        use_faster_whisper: bool | None = None,
        subprocess_runner: Callable[[Path], dict] | None = None,
    ) -> None:
        self._settings = settings
        self._storage_dir = (storage_dir or self._settings.storage_dir).resolve()
        self._use_faster_whisper = self._settings.use_faster_whisper if use_faster_whisper is None else use_faster_whisper
        self._subprocess_runner = subprocess_runner
        self._openai_client: AsyncOpenAI | None = openai_client
        if self._openai_client is None and self._settings.openai_api_key and self._settings.openai_api_key != "sk-placeholder":
            self._openai_client = AsyncOpenAI(
                api_key=self._settings.openai_api_key,
                timeout=self._settings.openai_timeout_seconds,
            )

    async def transcribe(self, storage_key: str) -> dict:
        audio_path = (self._storage_dir / storage_key).resolve()
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if self._use_faster_whisper:
            try:
                if self._subprocess_runner is None:
                    payload = await asyncio.to_thread(self._transcribe_subprocess, audio_path)
                else:
                    payload = await asyncio.to_thread(self._subprocess_runner, audio_path)
                return await self._postprocess_payload(payload, audio_path, source="faster_whisper")
            except Exception as faster_whisper_error:
                if self._openai_client is None:
                    raise
                try:
                    payload = await self._transcribe_openai(audio_path)
                    return await self._postprocess_payload(payload, audio_path, source="openai")
                except Exception as openai_error:
                    raise RuntimeError(
                        "Faster-Whisper transcription failed and OpenAI fallback also failed. "
                        f"faster_whisper={faster_whisper_error}; openai={openai_error}"
                    ) from openai_error

        if self._openai_client is not None:
            payload = await self._transcribe_openai(audio_path)
            return await self._postprocess_payload(payload, audio_path, source="openai")

        raise RuntimeError(
            "No transcription backend configured. Enable USE_FASTER_WHISPER "
            "or provide OPENAI_API_KEY for OPENAI_TRANSCRIBE_MODEL."
        )

    async def _transcribe_openai(self, audio_path: Path) -> dict:
        if self._openai_client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        with audio_path.open("rb") as audio_file:
            response = await self._openai_client.audio.transcriptions.create(
                model=self._settings.openai_transcribe_model,
                file=audio_file,
                prompt=(
                    "Transcribe speech only if it is English or Hindi. "
                    "Return transcript in Roman script only (English/Hinglish). "
                    "If speech is in any other language, return empty transcript."
                ),
            )

        transcript_text = (getattr(response, "text", "") or "").strip()
        detected_language = getattr(response, "language", None)
        return {
            "transcript_text": transcript_text,
            "detected_language": detected_language,
            "model_name": self._settings.openai_transcribe_model,
            "processing_seconds": None,
        }

    async def _postprocess_payload(self, payload: dict, audio_path: Path, source: str) -> dict:
        text = self._normalize_transcript_text(payload.get("transcript_text"))
        detected_language = str(payload.get("detected_language") or "").strip().lower()

        unsupported_language = bool(detected_language) and detected_language not in _ALLOWED_LANGUAGE_CODES
        invalid_script = bool(text) and not self._is_latin_script_text(text)

        # If Faster-Whisper returns unsupported language/script, try OpenAI once.
        if source != "openai" and self._openai_client is not None and (unsupported_language or invalid_script or not text):
            try:
                openai_payload = await self._transcribe_openai(audio_path)
                return await self._postprocess_payload(openai_payload, audio_path, source="openai")
            except Exception:
                pass

        if unsupported_language or invalid_script:
            payload["transcript_text"] = ""
            return payload

        payload["transcript_text"] = text
        return payload

    @staticmethod
    def _normalize_transcript_text(value: object) -> str:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return ""
        # Strip control chars and collapse extra spaces.
        text = re.sub(r"[\u0000-\u001f\u007f]+", " ", text).strip()
        return " ".join(text.split())

    @staticmethod
    def _is_latin_script_text(text: str) -> bool:
        has_alpha = False
        for char in text:
            if not char.isalpha():
                continue
            has_alpha = True
            name = unicodedata.name(char, "")
            if "LATIN" not in name:
                return False
        return has_alpha

    def _transcribe_subprocess(self, audio_path: Path) -> dict:
        # On Windows, force CPU + float32 to avoid CTranslate2 access violations.
        if sys.platform == "win32":
            device = "cpu"
            compute_type = "float32"
        else:
            device = self._settings.faster_whisper_device
            compute_type = self._settings.faster_whisper_compute_type

        # Pass thread-limiting env vars to the subprocess.
        # CTranslate2 crashes on Windows when it tries to spawn multiple CPU
        # threads at DLL initialisation time (STATUS_ACCESS_VIOLATION).
        # Limiting every BLAS/OpenMP layer to 1 thread prevents the crash.
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "1"
        env["OPENBLAS_NUM_THREADS"] = "1"
        env["MKL_NUM_THREADS"] = "1"
        env["NUMEXPR_NUM_THREADS"] = "1"

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(_WORKER_SCRIPT),
                    str(audio_path),
                    self._settings.faster_whisper_model,
                    device,
                    compute_type,
                ],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Transcription subprocess timed out after 300 s for {audio_path.name}"
            ) from exc

        if result.returncode != 0:
            # Include stderr so the Celery retry log is useful
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            details: list[str] = []
            if stderr:
                details.append(f"stderr={stderr}")
            if stdout:
                details.append(f"stdout={stdout}")
            raise RuntimeError(
                f"Transcription subprocess exited with code {result.returncode}"
                + (f": {'; '.join(details)}" if details else "")
            )

        stdout = result.stdout.strip()
        if not stdout:
            raise RuntimeError("Transcription subprocess produced no output.")

        return json.loads(stdout)
