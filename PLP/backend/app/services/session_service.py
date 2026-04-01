from __future__ import annotations

import secrets

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.answer import CandidateAnswer
from app.models.questions import Question
from app.models.sessions import CandidateSession
from app.models.user import User
from app.schemas.candidate import CandidateAnswerDetail, CandidateSessionDetail, CandidateSessionQuestion
from app.services.audio_service import AudioService
from app.services.module_service import ModuleService
from app.utils.helpers import utcnow


class SessionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audio_service = AudioService()
        self.module_service = ModuleService(db)

    async def start_session(self, user: User, module_slug: str) -> CandidateSession:
        module = await self.module_service.get_module_by_slug(module_slug)
        questions = await self.module_service.get_random_questions(module.id, module.question_count)
        started_at = utcnow()

        session = CandidateSession(
            user_id=user.id,
            module_id=module.id,
            auth0_id=user.auth0_user_id,
            name=user.full_name,
            email=user.email,
            session_token=secrets.token_urlsafe(16),
            login_at=started_at,
        )
        self.db.add(session)
        await self.db.flush()

        for question in questions:
            self.db.add(
                CandidateAnswer(
                    session_id=session.id,
                    question_id=question.id,
                    user_id=user.id,
                    audio_storage_key="",
                )
            )

        await self.db.commit()
        return await self.get_owned_session(user.id, session.id)

    async def get_owned_session(self, user_id: str | int, session_id: str | int) -> CandidateSession:
        result = await self.db.execute(
            select(CandidateSession)
            .where(CandidateSession.id == int(session_id), CandidateSession.user_id == int(user_id))
            .options(
                selectinload(CandidateSession.user),
                selectinload(CandidateSession.module),
                selectinload(CandidateSession.answers)
                .selectinload(CandidateAnswer.question)
                .selectinload(Question.standard_responses),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.transcript),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.ai_evaluation),
                selectinload(CandidateSession.manual_scores),
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        return session

    async def upload_answer_audio(
        self,
        user_id: str | int,
        session_id: str | int,
        question_id: str | int,
        upload: UploadFile,
    ) -> CandidateAnswer:
        session = await self.get_owned_session(user_id, session_id)
        if session.submitted_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is already submitted.")

        result = await self.db.execute(
            select(CandidateAnswer).where(
                CandidateAnswer.session_id == session.id,
                CandidateAnswer.question_id == int(question_id),
                CandidateAnswer.user_id == int(user_id),
            )
        )
        answer = result.scalar_one_or_none()
        if answer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer slot not found.")

        answer.audio_storage_key = await self.audio_service.save_candidate_recording(upload, str(session.id), str(question_id))
        await self.db.commit()
        await self.db.refresh(answer)
        return answer

    async def submit_session(self, user_id: str | int, session_id: str | int) -> CandidateSession:
        session = await self.get_owned_session(user_id, session_id)
        recorded_answers = [answer for answer in session.answers if answer.audio_storage_key]
        if len(recorded_answers) != len(session.answers):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All assigned questions must have a recorded response before submission.",
            )

        session.submitted_at = utcnow()
        await self.db.commit()
        from app.workers.tasks import process_candidate_session

        process_candidate_session.delay(str(session.id))
        return session

    async def build_session_detail(self, session: CandidateSession) -> CandidateSessionDetail:
        answers = []
        for display_order, answer in enumerate(sorted(session.answers, key=lambda item: item.id), start=1):
            evaluation = answer.ai_evaluation
            answers.append(
                CandidateAnswerDetail(
                    answer_id=str(answer.id),
                    question_id=str(answer.question.id),
                    question_code=answer.question.question_code,
                    question_title=answer.question.title,
                    display_order=display_order,
                    status=answer.status.value,
                    question_audio_url=self.audio_service.question_audio_url(answer.question.audio_storage_key),
                    audio_url=self.audio_service.candidate_audio_url(answer.audio_storage_key),
                    transcript_text=answer.transcript.transcript_text if answer.transcript else None,
                    standard_responses=[],
                    evaluation=self._serialize_evaluation(evaluation),
                )
            )

        return CandidateSessionDetail(
            session_id=str(session.id),
            candidate_id=session.user.candidate_code,
            status=session.status.value,
            module_slug=session.module.slug,
            module_title=session.module.title,
            login_at=session.login_at,
            started_at=session.started_at,
            submitted_at=session.submitted_at,
            completed_at=session.completed_at,
            ai_score=session.ai_score,
            answers=answers,
        )

    def build_start_response(self, session: CandidateSession) -> dict:
        questions = [
            CandidateSessionQuestion(
                question_id=str(answer.question.id),
                question_code=answer.question.question_code,
                title=answer.question.title,
                scenario_transcript=answer.question.scenario_transcript or answer.question.title,
                audio_url=self.audio_service.question_audio_url(answer.question.audio_storage_key),
                display_order=index,
            )
            for index, answer in enumerate(sorted(session.answers, key=lambda item: item.id), start=1)
        ]
        return {
            "session_id": str(session.id),
            "candidate_id": session.user.candidate_code,
            "module_slug": session.module.slug,
            "module_title": session.module.title,
            "status": session.status.value,
            "questions": questions,
        }

    def _serialize_evaluation(self, evaluation) -> dict | None:
        if evaluation is None:
            return None
        return {
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
