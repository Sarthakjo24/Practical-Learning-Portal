from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentToken, CurrentUser
from app.core.config import settings
from app.schemas.auth import UserProfileResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserProfileResponse)
async def get_current_profile(user: CurrentUser, token: CurrentToken) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        candidate_code=user.candidate_code,
        full_name=user.full_name,
        email=user.email,
        avatar_url=user.avatar_url,
        last_login_at=user.last_login_at,
        is_admin=settings.auth0_admin_role in token.roles or "admin:portal" in token.permissions,
    )
