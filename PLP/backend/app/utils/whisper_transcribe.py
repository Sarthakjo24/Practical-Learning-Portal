"""Standalone faster-whisper transcription worker.

Run as a subprocess to isolate CTranslate2 / native DLL crashes from the
parent Celery process.  If CTranslate2 triggers an access violation
(Windows exit code 3221225477) the subprocess dies but the Celery worker
survives and can retry via its autoretry_for mechanism.

Usage (internal — called by TranscriptionService):
    python whisper_transcribe.py <audio_path> <model_name> [device] [compute_type]

Outputs a single line of JSON to stdout on success.
Writes error messages to stderr on failure.
"""
from __future__ import annotations

import json
import sys
import time


def main() -> None:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: whisper_transcribe.py <audio_path> <model_name> [device] [compute_type]"}))
        sys.exit(1)

    audio_path = sys.argv[1]
    model_name = sys.argv[2]
    device = sys.argv[3] if len(sys.argv) > 3 else "cpu"
    compute_type = sys.argv[4] if len(sys.argv) > 4 else "float32"

    from faster_whisper import WhisperModel  # noqa: PLC0415

    started = time.perf_counter()
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, info = model.transcribe(audio_path)
    transcript = " ".join(seg.text.strip() for seg in segments if seg.text).strip()

    result = {
        "transcript_text": transcript,
        "detected_language": getattr(info, "language", None),
        "model_name": model_name,
        "processing_seconds": round(time.perf_counter() - started, 3),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
