from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.sessions import CandidateSession
from app.models.user import User
from app.utils.helpers import utcnow


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def sync_auth0_user(
        self,
        auth0_user_id: str,
        email: str,
        full_name: str,
        avatar_url: str | None,
    ) -> User:
        del avatar_url
        normalized_email = email.strip().lower()
        provider = auth0_user_id.split("|", 1)[0] if "|" in auth0_user_id else "auth0"
        result = await self.db.execute(select(User).where(User.auth0_user_id == auth0_user_id))
        user = result.scalar_one_or_none()

        if user is None:
            email_match = await self.db.execute(select(User).where(User.email == normalized_email))
            user = email_match.scalar_one_or_none()

        if user is None:
            user = User(
                auth0_user_id=auth0_user_id,
                full_name=full_name,
                email=normalized_email,
                provider=provider,
                role="admin" if settings.is_admin_email(normalized_email) else "candidate",
            )
            self.db.add(user)
        else:
            user.auth0_user_id = auth0_user_id
            user.full_name = full_name
            user.email = normalized_email
            user.provider = provider or user.provider
            user.role = "admin" if (settings.is_admin_email(normalized_email) or user.is_admin) else "candidate"

        await self.db.commit()
        await self.db.refresh(user)
        user.last_login_at = utcnow()
        return user

    async def get_user_by_id(self, user_id: str | int) -> User | None:
        user = await self.db.get(User, int(user_id))
        if user is None:
            return None

        result = await self.db.execute(
            select(CandidateSession)
            .where(CandidateSession.user_id == user.id)
            .order_by(desc(CandidateSession.login_at))
            .limit(1)
        )
        latest_session = result.scalar_one_or_none()
        user.last_login_at = latest_session.login_at if latest_session is not None else utcnow()
        return user
