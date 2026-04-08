import asyncio
import sys
from backend.app.core.database import AsyncSessionLocal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.app.models.sessions import CandidateSession

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CandidateSession)
            .where(CandidateSession.id.in_([9, 15, 17]))
            .options(
                selectinload(CandidateSession.answers).selectinload(CandidateSession.answers.property.mapper.class_.ai_evaluation)
            )
        )
        sessions = result.scalars().all()
        for session in sessions:
            evals = sum(1 for a in session.answers if getattr(a, "ai_evaluation", None) is not None)
            print(f"Session {session.id}: answers={len(session.answers)}, evals={evals}, status_prop={session.status}")

if __name__ == "__main__":
    asyncio.run(main())
