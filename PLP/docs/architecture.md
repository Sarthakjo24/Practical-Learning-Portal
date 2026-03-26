# Architecture Overview

## Core Flow

1. Candidate logs in through Auth0 with Google or Microsoft.
2. Frontend sends the Auth0 access token to FastAPI.
3. FastAPI validates JWT, upserts the user, and returns the internal candidate identity.
4. Candidate starts a session for a module.
5. Backend selects five randomized active questions from MySQL.
6. Frontend streams recorded audio to FastAPI and stores files under local project storage for now.
7. Candidate submits the session.
8. Celery worker transcribes each response with Faster Whisper.
9. Worker evaluates behavior against 4-5 standard responses using the centralized prompt template stored in `evaluation_configs`.
10. Worker stores transcripts, AI evaluations, and an aggregate AI score in MySQL.
11. Admin reviews the candidate session, AI insights, transcripts, and can submit a manual score override.

## Key Design Decisions

- Questions, standard responses, and evaluation configs are database-driven so new modules can be added without code changes.
- Candidate recordings are stored locally under the project folder for development but behind a storage service abstraction for later S3 migration.
- The AI score is behavior-based and explicitly penalizes technical troubleshooting-heavy responses.
- Background processing isolates expensive transcription and evaluation work from the request path.
- Audit logs capture system and admin actions for traceability.
