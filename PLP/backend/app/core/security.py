from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings


class TokenPayload(BaseModel):
    sub: str
    email: EmailStr
    name: str = "Unknown User"
    picture: str | None = None
    permissions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)


@lru_cache
def get_jwks_client() -> PyJWKClient:
    return PyJWKClient(settings.auth0_jwks_url)


class Auth0JWTBearer(HTTPBearer):
    async def __call__(self, request) -> TokenPayload:  # type: ignore[override]
        credentials: HTTPAuthorizationCredentials | None = await super().__call__(request)
        if credentials is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
        return verify_token(credentials.credentials)


def verify_token(token: str) -> TokenPayload:
    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=settings.auth0_issuer,
        )
    except Exception as exc:  # pragma: no cover - external token failures
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        ) from exc

    roles = payload.get("https://plp.example.com/roles") or payload.get("roles") or []
    permissions = payload.get("permissions") or []
    return TokenPayload(
        sub=payload["sub"],
        email=payload["email"],
        name=payload.get("name", "Unknown User"),
        picture=payload.get("picture"),
        permissions=permissions,
        roles=roles,
    )


auth_scheme = Auth0JWTBearer(auto_error=True)


def ensure_admin(payload: TokenPayload) -> TokenPayload:
    if settings.auth0_admin_role not in payload.roles and "admin:portal" not in payload.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return payload
