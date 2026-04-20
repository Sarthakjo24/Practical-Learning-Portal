from __future__ import annotations

from typing import Any


class EvaluationPayloadParser:
    @staticmethod
    def require_overall_summary(payload: dict[str, Any]) -> dict[str, Any]:
        summary = str(payload.get("overall_summary") or "").strip()
        if not summary:
            raise ValueError("Missing overall_summary in model output.")
        return payload
