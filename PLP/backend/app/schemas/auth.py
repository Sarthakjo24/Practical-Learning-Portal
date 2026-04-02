from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserProfileResponse(BaseModel):
    id: str
    candidate_code: str
    full_name: str
    email: EmailStr
    avatar_url: str | None = None
    last_login_at: datetime
    is_admin: bool
    can_access_admin: bool


class AuthMessageResponse(BaseModel):
    message: str
