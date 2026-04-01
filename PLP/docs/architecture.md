# Architecture Overview

## Core Flow

1. Candidate clicks Google or Microsoft sign-in on the frontend.
2. Frontend redirects the browser to a FastAPI Auth0 login endpoint.
3. FastAPI redirects the browser to Auth0.
4. Auth0 returns the authorization code to FastAPI.
5. FastAPI exchanges the code, verifies the Auth0 ID token, upserts the user, and issues a signed session cookie.
6. Frontend calls session-backed APIs with browser cookies.
7. Candidate starts a session for a module.
8. Backend selects five randomized active questions from MySQL.
9. Frontend streams recorded audio to FastAPI and stores files under local project storage for now.
10. Candidate submits the session.
11. Celery worker transcribes each response with Faster Whisper.
12. Worker evaluates behavior against 4-5 standard responses using the centralized prompt template stored in `evaluation_configs`.
13. Worker stores transcripts, AI evaluations, and an aggregate AI score in MySQL.
14. Admin reviews the candidate session, AI insights, transcripts, and can submit a manual score override.

## Key Design Decisions

- Questions, standard responses, and evaluation configs are database-driven so new modules can be added without code changes.
- Candidate recordings are stored locally under the project folder for development but behind a storage service abstraction for later S3 migration.
- The AI score is behavior-based and explicitly penalizes technical troubleshooting-heavy responses.
- Background processing isolates expensive transcription and evaluation work from the request path.
- Audit logs capture system and admin actions for traceability.
