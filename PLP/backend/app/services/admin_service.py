from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_evaluation import AdminScore, AuditLog
from app.models.answer import CandidateAnswer
from app.models.questions import Module, Question
from app.models.sessions import CandidateSession, SessionQuestion
from app.models.user import User
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
        statement = (
            select(CandidateSession)
            .options(
                selectinload(CandidateSession.user),
                selectinload(CandidateSession.module),
                selectinload(CandidateSession.manual_scores),
            )
            .order_by(CandidateSession.created_at.desc())
        )

        if module_slug:
            statement = statement.join(Module, CandidateSession.module_id == Module.id).where(Module.slug == module_slug)
        if status_filter:
            statement = statement.where(CandidateSession.status == status_filter)
        if candidate_id:
            statement = statement.join(User, CandidateSession.user_id == User.id).where(User.candidate_code == candidate_id)
        if email:
            statement = statement.join(User, CandidateSession.user_id == User.id).where(User.email == email)

        total = await self.db.scalar(select(func.count()).select_from(statement.subquery()))
        result = await self.db.execute(statement.offset((page - 1) * page_size).limit(page_size))
        sessions = list(result.scalars().unique().all())

        items = []
        for session in sessions:
            latest_manual = session.manual_scores[0] if session.manual_scores else None
            items.append(
                AdminCandidateListItem(
                    session_id=session.id,
                    candidate_id=session.user.candidate_code,
                    name=session.user.full_name,
                    email=session.user.email,
                    module_title=session.module.title,
                    status=session.status.value,
                    ai_score=float(session.ai_score) if session.ai_score is not None else None,
                    evaluator_score=float(latest_manual.manual_score) if latest_manual else None,
                    submission_time=session.submitted_at,
                    login_time=session.login_at,
                )
            )

        return AdminCandidateListResponse(
            page=page,
            page_size=page_size,
            total=total or 0,
            items=items,
        )

    async def get_candidate_detail(self, session_id: str) -> AdminCandidateDetail:
        result = await self.db.execute(
            select(CandidateSession)
            .where(CandidateSession.id == session_id)
            .options(
                selectinload(CandidateSession.user),
                selectinload(CandidateSession.module),
                selectinload(CandidateSession.manual_scores),
                selectinload(CandidateSession.assigned_questions).selectinload(SessionQuestion.question),
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

        ordered_questions = {item.question_id: item.display_order for item in session.assigned_questions}
        answers = []
        for answer in sorted(session.answers, key=lambda item: ordered_questions.get(item.question_id, 999)):
            evaluation = answer.ai_evaluation
            answers.append(
                {
                    "answer_id": answer.id,
                    "question_id": answer.question.id,
                    "question_code": answer.question.question_code,
                    "question_title": answer.question.title,
                    "display_order": ordered_questions.get(answer.question_id, 0),
                    "status": answer.status.value,
                    "question_audio_url": self.audio_service.question_audio_url(answer.question.audio_storage_key),
                    "audio_url": self.audio_service.candidate_audio_url(answer.audio_storage_key),
                    "transcript_text": answer.transcript.transcript_text if answer.transcript else None,
                    "standard_responses": [
                        item.response_text
                        for item in answer.question.standard_responses
                        if item.is_active
                    ],
                    "evaluation": (
                        {
                            "total_score": float(evaluation.total_score),
                            "courtesy_score": float(evaluation.courtesy_score),
                            "respect_score": float(evaluation.respect_score),
                            "empathy_score": float(evaluation.empathy_score),
                            "sympathy_score": float(evaluation.sympathy_score),
                            "tone_score": float(evaluation.tone_score),
                            "communication_clarity_score": float(evaluation.communication_clarity_score),
                            "engagement_score": float(evaluation.engagement_score),
                            "problem_handling_approach_score": float(evaluation.problem_handling_approach_score),
                            "strengths": evaluation.strengths,
                            "improvement_areas": evaluation.improvement_areas,
                            "final_summary": evaluation.final_summary,
                            "confidence_score": float(evaluation.confidence_score)
                            if evaluation.confidence_score is not None
                            else None,
                        }
                        if evaluation
                        else None
                    ),
                }
            )

        latest_manual = session.manual_scores[0] if session.manual_scores else None
        return AdminCandidateDetail(
            session_id=session.id,
            candidate_id=session.user.candidate_code,
            name=session.user.full_name,
            email=session.user.email,
            module_slug=session.module.slug,
            module_title=session.module.title,
            status=session.status.value,
            ai_score=float(session.ai_score) if session.ai_score is not None else None,
            latest_manual_score=(
                {
                    "id": latest_manual.id,
                    "admin_email": latest_manual.admin_email,
                    "manual_score": float(latest_manual.manual_score),
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

    async def create_manual_score(self, session_id: str, admin_email: str, score: float, notes: str | None) -> AdminScore:
        session = await self.db.get(CandidateSession, session_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate session not found.")

        manual_score = AdminScore(
            session_id=session_id,
            admin_email=admin_email,
            manual_score=score,
            notes=notes,
        )
        self.db.add(manual_score)
        self.db.add(
            AuditLog(
                actor_type="admin",
                actor_id=admin_email,
                action="manual_score_set",
                entity_type="candidate_session",
                entity_id=session_id,
                metadata={"manual_score": score, "notes": notes},
            )
        )
        await self.db.commit()
        await self.db.refresh(manual_score)
        return manual_score

    async def delete_candidate(self, session_id: str, admin_email: str) -> None:
        result = await self.db.execute(
            select(CandidateSession)
            .where(CandidateSession.id == session_id)
            .options(selectinload(CandidateSession.answers))
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate session not found.")

        for answer in session.answers:
            self.audio_service.delete_storage_key(answer.audio_storage_key)

        self.db.add(
            AuditLog(
                actor_type="admin",
                actor_id=admin_email,
                action="candidate_deleted",
                entity_type="candidate_session",
                entity_id=session_id,
                metadata={"answer_count": len(session.answers)},
            )
        )
        await self.db.delete(session)
        await self.db.commit()
