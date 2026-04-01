from __future__ import annotations

import re
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Cookie, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from jwt import PyJWKClient

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.security import SessionPrincipal, create_session_token
from app.schemas.auth import AuthMessageResponse, UserProfileResponse
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_kwargs(max_age_seconds: int | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "path": "/",
    }
    if settings.session_cookie_domain:
        payload["domain"] = settings.session_cookie_domain
    if max_age_seconds is not None:
        payload["max_age"] = max_age_seconds
    return payload


def _safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/dashboard"
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/dashboard"
    return next_path


def _extract_name_from_claims(claims: dict) -> str:
    direct_name = " ".join(str(claims.get("name") or "").strip().split())
    if direct_name and "@" not in direct_name:
        return direct_name

    given = " ".join(str(claims.get("given_name") or "").strip().split())
    family = " ".join(str(claims.get("family_name") or "").strip().split())
    combined = " ".join(part for part in [given, family] if part)
    if combined:
        return combined

    email = str(claims.get("email") or "").strip().lower()
    local = email.split("@", 1)[0]
    parts = [item for item in re.split(r"[._+\-\s]+", local) if item]
    return " ".join(part.title() for part in parts) if parts else "Candidate"


def _verify_auth0_id_token(id_token: str) -> dict:
    jwks_client = PyJWKClient(f"{settings.auth0_issuer}.well-known/jwks.json")
    signing_key = jwks_client.get_signing_key_from_jwt(id_token).key
    return jwt.decode(
        id_token,
        signing_key,
        algorithms=["RS256"],
        audience=settings.auth0_client_id,
        issuer=settings.auth0_issuer,
    )


def _issue_session_cookie(response: Response, user_id: str, email: str, provider: str) -> None:
    token = create_session_token(
        SessionPrincipal(
            user_id=user_id,
            email=email,
            provider=provider,
        )
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        **_cookie_kwargs(max_age_seconds=settings.session_ttl_minutes * 60),
    )


def _clear_cookie(response: Response, key: str) -> None:
    response.delete_cookie(key=key, path="/", domain=settings.session_cookie_domain)


def _provider_connection(provider: str) -> str:
    if provider == "google":
        return settings.auth0_google_connection
    if provider == "microsoft":
        return settings.auth0_microsoft_connection
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported SSO provider.")


@router.get("/session", response_model=UserProfileResponse)
@router.get("/me", response_model=UserProfileResponse)
async def get_current_profile(user: CurrentUser) -> UserProfileResponse:
    return UserProfileResponse(
        id=str(user.id),
        candidate_code=user.candidate_code,
        full_name=user.full_name or user.email or "Candidate",
        email=user.email or "unknown@example.com",
        avatar_url=user.avatar_url,
        last_login_at=user.last_login_at,
        is_admin=settings.is_admin_email(user.email or ""),
    )


@router.post("/logout", response_model=AuthMessageResponse)
async def logout() -> Response:
    response = JSONResponse(content=AuthMessageResponse(message="Logged out successfully.").model_dump())
    _clear_cookie(response, settings.session_cookie_name)
    return response


@router.get("/auth0/login")
async def auth0_login(
    provider: str = Query(..., pattern="^(google|microsoft)$"),
    next_path: str | None = Query(default="/dashboard", alias="next"),
):
    state = secrets.token_urlsafe(24)
    safe_next = _safe_next_path(next_path)
    query = {
        "response_type": "code",
        "client_id": settings.auth0_client_id,
        "redirect_uri": settings.auth0_callback_url,
        "scope": "openid profile email",
        "state": state,
        "connection": _provider_connection(provider),
    }

    redirect_url = f"https://{settings.auth0_domain}/authorize?{urlencode(query)}"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie("oauth_state", state, **_cookie_kwargs(max_age_seconds=600))
    response.set_cookie("oauth_provider", provider, **_cookie_kwargs(max_age_seconds=600))
    response.set_cookie("oauth_next", safe_next, **_cookie_kwargs(max_age_seconds=600))
    return response


@router.get("/google")
async def google_login(next_path: str | None = Query(default="/dashboard", alias="next")):
    return await auth0_login(provider="google", next_path=next_path)


@router.get("/microsoft")
async def microsoft_login(next_path: str | None = Query(default="/dashboard", alias="next")):
    return await auth0_login(provider="microsoft", next_path=next_path)


@router.get("/callback")
async def auth0_callback(
    code: str,
    state: str,
    db: DBSession,
    oauth_state: str | None = Cookie(default=None),
    oauth_provider: str | None = Cookie(default=None),
    oauth_next: str | None = Cookie(default=None),
):
    if not oauth_state or oauth_state != state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")

    provider = oauth_provider or "google"
    safe_next = _safe_next_path(oauth_next)

    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            f"https://{settings.auth0_domain}/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": settings.auth0_client_id,
                "client_secret": settings.auth0_client_secret,
                "code": code,
                "redirect_uri": settings.auth0_callback_url,
            },
        )

    if token_response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange Auth0 authorization code.",
        )

    token_payload = token_response.json()
    id_token = token_payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing id_token from Auth0.")

    claims = _verify_auth0_id_token(id_token)
    email = str(claims.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Auth0 did not return an email.")

    user = await AuthService(db).sync_auth0_user(
        auth0_user_id=str(claims.get("sub") or email),
        email=email,
        full_name=_extract_name_from_claims(claims),
        avatar_url=str(claims.get("picture")) if claims.get("picture") else None,
    )

    target = f"{settings.frontend_base_url.rstrip('/')}{safe_next}"
    response = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    _issue_session_cookie(response, str(user.id), user.email or "", provider)
    _clear_cookie(response, "oauth_state")
    _clear_cookie(response, "oauth_provider")
    _clear_cookie(response, "oauth_next")
    return response
