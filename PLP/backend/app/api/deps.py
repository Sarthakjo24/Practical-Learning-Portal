from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import TokenPayload, auth_scheme, ensure_admin
from app.models.user import User
from app.services.auth_service import AuthService


async def get_token_payload(payload: TokenPayload = Depends(auth_scheme)) -> TokenPayload:
    return payload


async def get_admin_token_payload(payload: TokenPayload = Depends(auth_scheme)) -> TokenPayload:
    return ensure_admin(payload)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    payload: TokenPayload = Depends(get_token_payload),
) -> User:
    return await AuthService(db).sync_user(payload)


async def get_current_admin_user(
    db: AsyncSession = Depends(get_db),
    payload: TokenPayload = Depends(get_admin_token_payload),
) -> User:
    return await AuthService(db).sync_user(payload)


DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
CurrentToken = Annotated[TokenPayload, Depends(get_token_payload)]
CurrentAdminToken = Annotated[TokenPayload, Depends(get_admin_token_payload)]
