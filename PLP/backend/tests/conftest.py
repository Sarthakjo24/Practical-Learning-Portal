from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def evaluation_service():
    from app.services.evaluation_service import EvaluationService

    service = EvaluationService()
    service.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(),
            )
        )
    )
    service.max_retries = 3
    return service


@pytest.fixture
def transcription_service():
    from app.services.transcription_service import TranscriptionService

    service = TranscriptionService()
    service._openai_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(),
            )
        )
    )
    return service
