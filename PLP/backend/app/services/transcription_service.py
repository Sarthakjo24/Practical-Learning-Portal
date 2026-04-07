from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from app.core.config import settings

# Path to the isolated worker script
_WORKER_SCRIPT = Path(__file__).parent.parent / "utils" / "whisper_transcribe.py"


class TranscriptionService:
    async def transcribe(self, storage_key: str) -> dict:
        audio_path = (settings.storage_dir / storage_key).resolve()
        return await asyncio.to_thread(self._transcribe_subprocess, audio_path)

    def _transcribe_subprocess(self, audio_path: Path) -> dict:
        # On Windows, force CPU + float32 to avoid CTranslate2 access violations.
        # Even though we run in a subprocess (which isolates crashes from the
        # Celery worker), these settings also prevent the subprocess from hanging
        # waiting for GPU initialisation that doesn't exist.
        if sys.platform == "win32":
            device = "cpu"
            compute_type = "float32"
        else:
            device = settings.faster_whisper_device
            compute_type = settings.faster_whisper_compute_type

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(_WORKER_SCRIPT),
                    str(audio_path),
                    settings.faster_whisper_model,
                    device,
                    compute_type,
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5-minute hard limit per audio file
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Transcription subprocess timed out after 300 s for {audio_path.name}"
            ) from exc

        if result.returncode != 0:
            # Include stderr so the Celery retry log is useful
            stderr = result.stderr.strip()
            raise RuntimeError(
                f"Transcription subprocess exited with code {result.returncode}"
                + (f": {stderr}" if stderr else "")
            )

        stdout = result.stdout.strip()
        if not stdout:
            raise RuntimeError("Transcription subprocess produced no output.")

        return json.loads(stdout)
