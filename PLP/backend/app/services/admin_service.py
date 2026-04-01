from __future__ import annotations

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
                    evaluator_score=float(latest_manual.manual_score or 0) if latest_manual else None,
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
            answers.append(
                {
                    "answer_id": str(answer.id),
                    "question_id": str(answer.question.id),
                    "question_code": answer.question.question_code,
                    "question_title": answer.question.title,
                    "display_order": display_order,
                    "status": answer.status.value,
                    "question_audio_url": self.audio_service.question_audio_url(answer.question.audio_storage_key),
                    "audio_url": self.audio_service.candidate_audio_url(answer.audio_storage_key),
                    "transcript_text": answer.transcript.transcript_text if answer.transcript else None,
                    "standard_responses": [item.response_text for item in answer.question.standard_responses],
                    "evaluation": (
                        {
                            "total_score": float(evaluation.total_score or 0),
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
                            "final_summary": evaluation.final_summary or "",
                            "confidence_score": evaluation.confidence_score,
                        }
                        if evaluation
                        else None
                    ),
                }
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
            latest_manual_score=(
                {
                    "id": str(latest_manual.id),
                    "admin_email": latest_manual.admin_email,
                    "manual_score": float(latest_manual.manual_score or 0),
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

        manual_score.manual_score = score
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
