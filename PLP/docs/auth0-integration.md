# Auth0 Integration Guide

## Auth0 Setup

Create:

- One SPA application for the React frontend
- One Auth0 API with audience `https://plp.api`

Enable identity providers:

- Google OAuth2
- Microsoft Account or Entra ID

## Frontend Settings

Allowed callback URLs:

- `http://localhost:5173`
- `https://portal.example.com`

Allowed logout URLs:

- `http://localhost:5173`
- `https://portal.example.com`

Allowed web origins:

- `http://localhost:5173`
- `https://portal.example.com`

## Backend Expectations

The backend validates:

- issuer: `https://{AUTH0_DOMAIN}/`
- audience: `AUTH0_AUDIENCE`
- JWKS: `https://{AUTH0_DOMAIN}/.well-known/jwks.json`

Admin access is granted when the token includes the configured `AUTH0_ADMIN_ROLE` or permission `admin:portal`.
