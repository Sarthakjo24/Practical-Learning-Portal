from __future__ import annotations

from statistics import mean


class ScoringService:
    @staticmethod
    def aggregate_session_score(scores: list[float]) -> float | None:
        if not scores:
            return None
        return round(mean(scores), 2)
