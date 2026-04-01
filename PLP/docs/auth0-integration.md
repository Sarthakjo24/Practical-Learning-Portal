# Auth0 Integration Guide

## Auth0 Setup

Create one Auth0 application of type `Regular Web Application`.

Enable identity providers:

- Google OAuth2
- Microsoft Account or Entra ID

## Application Settings

Use these local values:

- Allowed Callback URLs: `http://localhost:8000/api/v1/auth/callback`
- Allowed Logout URLs: `http://localhost:5173/login`
- Allowed Web Origins: `http://localhost:5173,http://localhost:8000`
- Application Login URL: `http://localhost:5173/login`

Leave Cross-Origin Authentication disabled and leave Cross-Origin Verification Fallback URL blank.

## Backend Expectations

The backend:

- redirects the browser to Auth0
- exchanges the authorization code on callback
- verifies the Auth0 ID token with Auth0 JWKS
- creates a signed session cookie for the app

Admin access is driven locally through the `ADMIN_EMAILS` allowlist in `backend/.env`.
