from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenPayload
from app.models.user import User
from app.utils.helpers import generate_candidate_code, utcnow


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def sync_user(self, payload: TokenPayload) -> User:
        result = await self.db.execute(select(User).where(User.auth0_user_id == payload.sub))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                auth0_user_id=payload.sub,
                candidate_code=await self._next_candidate_code(),
                full_name=payload.name,
                email=str(payload.email),
                avatar_url=payload.picture,
                last_login_at=utcnow(),
            )
            self.db.add(user)
        else:
            user.full_name = payload.name
            user.email = str(payload.email)
            user.avatar_url = payload.picture
            user.last_login_at = utcnow()

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def _next_candidate_code(self) -> str:
        while True:
            candidate_code = generate_candidate_code()
            statement: Select[tuple[User]] = select(User).where(User.candidate_code == candidate_code)
            existing = await self.db.execute(statement)
            if existing.scalar_one_or_none() is None:
                return candidate_code
