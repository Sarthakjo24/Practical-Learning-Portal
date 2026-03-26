# Backend API Structure

Base prefix: `/api/v1`

## Shared

- `GET /health`
- `GET /modules`

## Auth

- `GET /auth/me`

Response:

```json
{
  "id": "uuid",
  "candidate_code": "CAND-20260326-ABC123",
  "full_name": "Jane Doe",
  "email": "jane@example.com",
  "avatar_url": "https://...",
  "last_login_at": "2026-03-26T10:00:00",
  "is_admin": false
}
```

## Candidate

- `POST /candidate/sessions`
- `GET /candidate/sessions/{session_id}`
- `POST /candidate/sessions/{session_id}/answers/{question_id}/audio`
- `POST /candidate/sessions/{session_id}/submit`

Start session request:

```json
{
  "module_slug": "practical-learning-portal"
}
```

## Admin

- `GET /admin/candidates`
- `GET /admin/candidates/{session_id}`
- `PUT /admin/candidates/{session_id}/manual-score`
- `DELETE /admin/candidates/{session_id}`

Manual score request:

```json
{
  "manual_score": 83,
  "notes": "Good empathy and tone, but closure could be stronger."
}
```

## Evaluation Config Management

- `GET /evaluation/configs/{module_slug}`
- `PUT /evaluation/configs/{module_slug}`
