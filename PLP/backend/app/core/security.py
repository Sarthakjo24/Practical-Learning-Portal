from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, HTTPException, status

from app.core.config import settings


@dataclass
class SessionPrincipal:
    user_id: str
    email: str
    provider: str


def create_session_token(principal: SessionPrincipal) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.session_ttl_minutes)
    payload = {
        "sub": principal.user_id,
        "email": principal.email,
        "provider": principal.provider,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.session_secret, algorithm=settings.session_algorithm)


def decode_session_token(token: str) -> SessionPrincipal:
    try:
        payload = jwt.decode(
            token,
            settings.session_secret,
            algorithms=[settings.session_algorithm],
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.") from exc

    user_id = payload.get("sub")
    email = payload.get("email")
    provider = payload.get("provider")
    if not user_id or not email or not provider:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session payload.")

    return SessionPrincipal(user_id=str(user_id), email=str(email), provider=str(provider))


def get_session_principal(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> SessionPrincipal:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return decode_session_token(session_token)
