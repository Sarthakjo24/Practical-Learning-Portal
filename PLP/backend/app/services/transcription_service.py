from __future__ import annotations

import asyncio
import json
import os
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
        if sys.platform == "win32":
            device = "cpu"
            compute_type = "float32"
        else:
            device = settings.faster_whisper_device
            compute_type = settings.faster_whisper_compute_type

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
                    settings.faster_whisper_model,
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
            raise RuntimeError(
                f"Transcription subprocess exited with code {result.returncode}"
                + (f": {stderr}" if stderr else "")
            )

        stdout = result.stdout.strip()
        if not stdout:
            raise RuntimeError("Transcription subprocess produced no output.")

        return json.loads(stdout)
