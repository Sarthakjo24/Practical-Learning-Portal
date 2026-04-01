from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import SessionPrincipal, get_session_principal
from app.models.user import User
from app.services.auth_service import AuthService


async def get_current_principal(principal: SessionPrincipal = Depends(get_session_principal)) -> SessionPrincipal:
    return principal


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    principal: SessionPrincipal = Depends(get_current_principal),
) -> User:
    user = await AuthService(db).get_user_by_id(principal.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user not found.")
    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if not settings.is_admin_email(user.email or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user


DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
CurrentPrincipal = Annotated[SessionPrincipal, Depends(get_current_principal)]
