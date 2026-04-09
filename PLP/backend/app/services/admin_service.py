from __future__ import annotations

import logging
from statistics import mean
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_evaluation import AdminScore
from app.models.answer import CandidateAnswer
from app.models.questions import Question
from app.models.sessions import CandidateSession
from app.schemas.admin import AdminCandidateDetail, AdminCandidateListItem, AdminCandidateListResponse
from app.services.audio_service import AudioService
from app.services.evaluation_service import EvaluationService


logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audio_service = AudioService()

    async def list_candidates(
        self,
        page: int,
        page_size: int,
        module_slug: str | None = None,
        status_filter: str | None = None,
        candidate_id: str | None = None,
        email: str | None = None,
    ) -> AdminCandidateListResponse:
        result = await self.db.execute(
            select(CandidateSession)
            .options(
                selectinload(CandidateSession.user),
                selectinload(CandidateSession.module),
                selectinload(CandidateSession.manual_scores),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.ai_evaluation),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.transcript),
            )
            .order_by(CandidateSession.login_at.desc())
        )
        sessions = list(result.scalars().unique().all())

        filtered: list[CandidateSession] = []
        for session in sessions:
            if module_slug and session.module.slug != module_slug:
                continue
            if status_filter and session.status.value != status_filter:
                continue
            if candidate_id and session.user.candidate_code != candidate_id:
                continue
            if email and (session.user.email or "").lower() != email.lower():
                continue
            filtered.append(session)

        total = len(filtered)
        sliced = filtered[(page - 1) * page_size : page * page_size]

        items = []
        for session in sliced:
            latest_manual = session.manual_scores[0] if session.manual_scores else None
            items.append(
                AdminCandidateListItem(
                    session_id=str(session.id),
                    candidate_id=session.user.candidate_code,
                    name=session.user.full_name or session.user.email or "Candidate",
                    email=session.user.email or "unknown@example.com",
                    module_title=session.module.title,
                    status=session.status.value,
                    ai_score=session.ai_score,
                    evaluator_score=round(float(latest_manual.manual_score or 0), 2) if latest_manual else None,
                    submission_time=session.submitted_at,
                    login_time=session.login_at,
                )
            )

        return AdminCandidateListResponse(page=page, page_size=page_size, total=total, items=items)

    async def get_candidate_detail(self, session_id: str | int) -> AdminCandidateDetail:
        result = await self.db.execute(
            select(CandidateSession)
            .where(CandidateSession.id == int(session_id))
            .options(
                selectinload(CandidateSession.user),
                selectinload(CandidateSession.module),
                selectinload(CandidateSession.manual_scores),
                selectinload(CandidateSession.answers)
                .selectinload(CandidateAnswer.question)
                .selectinload(Question.standard_responses),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.transcript),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.ai_evaluation),
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate session not found.")

        answers = []
        for display_order, answer in enumerate(sorted(session.answers, key=lambda item: item.id), start=1):
            evaluation = answer.ai_evaluation
            question = answer.question
            question_id = int(getattr(answer, "question_id", 0) or 0)
            fallback_code = f"Q-{question_id:03d}" if question_id > 0 else f"Q-MISSING-{answer.id}"
            serialized_evaluation = self._serialize_evaluation(evaluation)
            answers.append(
                {
                    "answer_id": str(answer.id),
                    "question_id": str(question.id if question is not None else question_id),
                    "question_code": question.question_code if question is not None else fallback_code,
                    "question_title": (
                        question.title
                        if question is not None
                        else f"Deleted question ({question_id})"
                    ),
                    "display_order": display_order,
                    "status": answer.status.value,
                    "question_audio_url": (
                        self.audio_service.question_audio_url(question.audio_storage_key)
                        if question is not None
                        else ""
                    ),
                    "audio_url": self.audio_service.candidate_audio_url(answer.audio_storage_key),
                    "transcript_text": answer.transcript.transcript_text if answer.transcript else None,
                    "standard_responses": (
                        [item.response_text for item in question.standard_responses]
                        if question is not None
                        else []
                    ),
                    "evaluation": serialized_evaluation,
                }
            )

        overall_performance_summary = await self._build_overall_performance_summary(
            session=session,
            serialized_answers=answers,
        )

        latest_manual = session.manual_scores[0] if session.manual_scores else None
        if latest_manual is not None:
            latest_manual.admin_email = latest_manual.admin_email

        return AdminCandidateDetail(
            session_id=str(session.id),
            candidate_id=session.user.candidate_code,
            name=session.user.full_name or session.user.email or "Candidate",
            email=session.user.email or "unknown@example.com",
            module_slug=session.module.slug,
            module_title=session.module.title,
            status=session.status.value,
            ai_score=session.ai_score,
            overall_performance_summary=overall_performance_summary,
            latest_manual_score=(
                {
                    "id": str(latest_manual.id),
                    "admin_email": latest_manual.admin_email,
                    "manual_score": round(float(latest_manual.manual_score or 0), 2),
                    "notes": latest_manual.notes,
                    "created_at": latest_manual.created_at,
                }
                if latest_manual
                else None
            ),
            login_time=session.login_at,
            submission_time=session.submitted_at,
            completed_at=session.completed_at,
            answers=answers,
        )

    async def create_manual_score(self, session_id: str | int, admin_email: str, score: float, notes: str | None) -> AdminScore:
        session = await self.db.get(CandidateSession, int(session_id))
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate session not found.")

        result = await self.db.execute(select(AdminScore).where(AdminScore.session_id == int(session_id)))
        manual_score = result.scalar_one_or_none()
        if manual_score is None:
            manual_score = AdminScore(session_id=int(session_id))
            self.db.add(manual_score)

        manual_score.manual_score = round(score, 2)
        manual_score.notes = notes
        manual_score.admin_email = admin_email

        await self.db.commit()
        await self.db.refresh(manual_score)
        manual_score.admin_email = admin_email
        return manual_score

    async def delete_candidate(self, session_id: str | int, admin_email: str) -> None:
        del admin_email
        result = await self.db.execute(
            select(CandidateSession)
            .where(CandidateSession.id == int(session_id))
            .options(selectinload(CandidateSession.answers))
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate session not found.")

        for answer in session.answers:
            self.audio_service.delete_storage_key(answer.audio_storage_key)

        await self.db.delete(session)
        await self.db.commit()

    def _serialize_evaluation(self, evaluation) -> dict | None:
        if evaluation is None:
            return None

        failure_markers = (
            "evaluation failed:",
            "audio processing failed:",
            "unable to parse evaluation result.",
        )
        summary = str(evaluation.final_summary or "").strip()
        if (
            evaluation.total_score is None
            or not summary
            or summary.lower().startswith(failure_markers)
            or len(evaluation.strengths) == 0
            or len(evaluation.improvement_areas) == 0
        ):
            return None

        return {
            "total_score": float(evaluation.total_score),
            "courtesy_score": float(evaluation.courtesy_score or 0),
            "respect_score": float(evaluation.respect_score or 0),
            "empathy_score": float(evaluation.empathy_score or 0),
            "sympathy_score": float(evaluation.sympathy_score or 0),
            "tone_score": float(evaluation.tone_score or 0),
            "communication_clarity_score": float(evaluation.communication_clarity_score or 0),
            "engagement_score": float(evaluation.engagement_score or 0),
            "problem_handling_approach_score": float(evaluation.problem_handling_approach_score or 0),
            "strengths": evaluation.strengths,
            "improvement_areas": evaluation.improvement_areas,
            "final_summary": summary,
            "confidence_score": evaluation.confidence_score,
        }

    async def _build_overall_performance_summary(
        self,
        session: CandidateSession,
        serialized_answers: list[dict[str, Any]],
    ) -> str | None:
        evaluated_answers: list[dict[str, Any]] = []
        for answer in serialized_answers:
            evaluation = answer.get("evaluation")
            if not isinstance(evaluation, dict):
                continue

            transcript = str(answer.get("transcript_text") or "").strip()
            transcript_excerpt = transcript[:600] + ("..." if len(transcript) > 600 else "")

            evaluated_answers.append(
                {
                    "question_code": answer.get("question_code"),
                    "question_title": answer.get("question_title"),
                    "transcript_excerpt": transcript_excerpt,
                    "total_score": evaluation.get("total_score"),
                    "courtesy_score": evaluation.get("courtesy_score"),
                    "respect_score": evaluation.get("respect_score"),
                    "empathy_score": evaluation.get("empathy_score"),
                    "tone_score": evaluation.get("tone_score"),
                    "communication_clarity_score": evaluation.get("communication_clarity_score"),
                    "engagement_score": evaluation.get("engagement_score"),
                    "problem_handling_approach_score": evaluation.get("problem_handling_approach_score"),
                    "strengths": evaluation.get("strengths", []),
                    "improvement_areas": evaluation.get("improvement_areas", []),
                }
            )

        if not evaluated_answers:
            return None

        candidate_name = session.user.full_name or session.user.email or "Candidate"
        candidate_id = str(session.user.candidate_code or "")

        summary_service = EvaluationService()
        if summary_service.client is not None:
            try:
                summary = await summary_service.summarize_candidate_performance(
                    module_title=session.module.title,
                    candidate_name=candidate_name,
                    candidate_id=candidate_id,
                    evaluated_answers=evaluated_answers,
                )
                if summary.strip():
                    return summary.strip()
            except Exception as exc:
                logger.warning(
                    "Falling back to heuristic overall summary for session %s: %s",
                    session.id,
                    exc,
                )

        return self._heuristic_overall_summary(evaluated_answers)

    def _heuristic_overall_summary(self, evaluated_answers: list[dict[str, Any]]) -> str | None:
        if not evaluated_answers:
            return None

        scores = []
        for answer in evaluated_answers:
            raw_score = answer.get("total_score")
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            scores.append(score)

        average_score = round(mean(scores), 2) if scores else None
        strengths = self._collect_unique_points(evaluated_answers, "strengths")
        improvement_areas = self._collect_unique_points(evaluated_answers, "improvement_areas")

        response_count = len(evaluated_answers)
        score_text = f" with an average score of {average_score:.2f}/10" if average_score is not None else ""
        strengths_text = ", ".join(strengths) if strengths else "polite tone and response structure"
        improvements_text = (
            ", ".join(improvement_areas)
            if improvement_areas
            else "showing more empathy and clearer problem-handling intent"
        )
        return (
            f"Across {response_count} evaluated responses{score_text}, the candidate showed recurring strengths in "
            f"{strengths_text}. The main opportunities to improve were {improvements_text}."
        )

    def _collect_unique_points(
        self,
        evaluated_answers: list[dict[str, Any]],
        field_name: str,
        limit: int = 3,
    ) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()
        for answer in evaluated_answers:
            for raw_item in answer.get(field_name, []) or []:
                item = str(raw_item or "").strip()
                if not item:
                    continue
                normalized = item.lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                results.append(item)
                if len(results) >= limit:
                    return results
        return results
