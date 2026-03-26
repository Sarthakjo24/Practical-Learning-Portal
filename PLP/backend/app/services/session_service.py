from __future__ import annotations

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_evaluation import AuditLog
from app.models.answer import AnswerStatus, CandidateAnswer
from app.models.sessions import CandidateSession, SessionQuestion, SessionStatus
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

        session = CandidateSession(
            user_id=user.id,
            module_id=module.id,
            status=SessionStatus.IN_PROGRESS,
            login_at=user.last_login_at,
            started_at=utcnow(),
        )
        self.db.add(session)
        await self.db.flush()

        for index, question in enumerate(questions, start=1):
            self.db.add(
                SessionQuestion(
                    session_id=session.id,
                    question_id=question.id,
                    display_order=index,
                )
            )
            self.db.add(
                CandidateAnswer(
                    session_id=session.id,
                    question_id=question.id,
                    status=AnswerStatus.PENDING,
                )
            )

        self.db.add(
            AuditLog(
                actor_type="candidate",
                actor_id=user.id,
                action="session_started",
                entity_type="candidate_session",
                entity_id=session.id,
                metadata={"module_id": module.id, "question_count": len(questions)},
            )
        )
        await self.db.commit()
        return await self.get_owned_session(user.id, session.id)

    async def get_owned_session(self, user_id: str, session_id: str) -> CandidateSession:
        result = await self.db.execute(
            select(CandidateSession)
            .where(CandidateSession.id == session_id, CandidateSession.user_id == user_id)
            .options(
                selectinload(CandidateSession.user),
                selectinload(CandidateSession.module),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.question),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.transcript),
                selectinload(CandidateSession.answers).selectinload(CandidateAnswer.ai_evaluation),
                selectinload(CandidateSession.assigned_questions).selectinload(SessionQuestion.question),
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        return session

    async def upload_answer_audio(
        self,
        user_id: str,
        session_id: str,
        question_id: str,
        upload: UploadFile,
    ) -> CandidateAnswer:
        session = await self.get_owned_session(user_id, session_id)
        if session.status in {SessionStatus.SUBMITTED, SessionStatus.PROCESSING, SessionStatus.COMPLETED}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is already submitted.")

        result = await self.db.execute(
            select(CandidateAnswer).where(
                CandidateAnswer.session_id == session.id,
                CandidateAnswer.question_id == question_id,
            )
        )
        answer = result.scalar_one_or_none()
        if answer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer slot not found.")

        answer.audio_storage_key = await self.audio_service.save_candidate_recording(upload, session.id, question_id)
        answer.status = AnswerStatus.RECORDED
        answer.submitted_at = utcnow()
        self.db.add(
            AuditLog(
                actor_type="candidate",
                actor_id=user_id,
                action="answer_uploaded",
                entity_type="candidate_answer",
                entity_id=answer.id,
                metadata={"session_id": session.id, "question_id": question_id},
            )
        )
        await self.db.commit()
        await self.db.refresh(answer)
        return answer

    async def submit_session(self, user_id: str, session_id: str) -> CandidateSession:
        session = await self.get_owned_session(user_id, session_id)
        recorded_answers = [answer for answer in session.answers if answer.audio_storage_key]
        if len(recorded_answers) != len(session.answers):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All assigned questions must have a recorded response before submission.",
            )

        session.status = SessionStatus.PROCESSING
        session.submitted_at = utcnow()
        for answer in session.answers:
            answer.status = AnswerStatus.SUBMITTED

        self.db.add(
            AuditLog(
                actor_type="candidate",
                actor_id=user_id,
                action="session_submitted",
                entity_type="candidate_session",
                entity_id=session.id,
                metadata={"answer_count": len(session.answers)},
            )
        )
        await self.db.commit()
        from app.workers.tasks import process_candidate_session

        process_candidate_session.delay(session.id)
        return session

    async def build_session_detail(self, session: CandidateSession) -> CandidateSessionDetail:
        ordered_questions = {entry.question_id: entry.display_order for entry in session.assigned_questions}
        answers = []
        for answer in sorted(session.answers, key=lambda item: ordered_questions.get(item.question_id, 999)):
            evaluation = answer.ai_evaluation
            answers.append(
                CandidateAnswerDetail(
                    answer_id=answer.id,
                    question_id=answer.question.id,
                    question_code=answer.question.question_code,
                    question_title=answer.question.title,
                    display_order=ordered_questions.get(answer.question_id, 0),
                    status=answer.status.value,
                    question_audio_url=self.audio_service.question_audio_url(answer.question.audio_storage_key),
                    audio_url=self.audio_service.candidate_audio_url(answer.audio_storage_key),
                    transcript_text=answer.transcript.transcript_text if answer.transcript else None,
                    standard_responses=[],
                    evaluation=(
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
                )
            )

        return CandidateSessionDetail(
            session_id=session.id,
            candidate_id=session.user.candidate_code,
            status=session.status.value,
            module_slug=session.module.slug,
            module_title=session.module.title,
            login_at=session.login_at,
            started_at=session.started_at,
            submitted_at=session.submitted_at,
            completed_at=session.completed_at,
            ai_score=float(session.ai_score) if session.ai_score is not None else None,
            answers=answers,
        )

    def build_start_response(self, session: CandidateSession) -> dict:
        questions = [
            CandidateSessionQuestion(
                question_id=assigned.question.id,
                question_code=assigned.question.question_code,
                title=assigned.question.title,
                scenario_transcript=assigned.question.scenario_transcript,
                audio_url=self.audio_service.question_audio_url(assigned.question.audio_storage_key),
                display_order=assigned.display_order,
            )
            for assigned in session.assigned_questions
        ]
        return {
            "session_id": session.id,
            "candidate_id": session.user.candidate_code,
            "module_slug": session.module.slug,
            "module_title": session.module.title,
            "status": session.status.value,
            "questions": questions,
        }
