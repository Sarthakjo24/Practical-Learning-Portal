# Practical Learning Portal

Practical Learning Portal is an AI-powered candidate assessment platform for behavior-based audio response evaluation. Candidates authenticate with Auth0, receive five randomized audio scenarios from a module, record spoken responses, and submit them for background transcription and AI evaluation. Admins review AI scores, transcripts, insights, and can apply manual overrides.

## Textual Architecture Diagram

```text
[React Frontend]
  |- Landing
  |- Login via Auth0
  |- Candidate dashboard
  |- Assessment recorder
  |- Submission confirmation
  |- Admin dashboard
            |
            v
[FastAPI API]
  |- Auth0 JWT validation
  |- Module/question retrieval from MySQL
  |- Candidate session orchestration
  |- Local candidate audio storage
  |- Admin APIs
            |
            +--> [MySQL / MariaDB]
            |
            +--> [Redis]
                    |
                    v
              [Celery Workers]
                |- Faster Whisper transcription
                |- OpenAI evaluation
                |- Score aggregation
                |- Audit logging
```

## Deliverables In Repo

- Architecture overview: [docs/architecture.md](/c:/Users/sarthak.joshi/Automation/PLP/docs/architecture.md)
- Backend API structure: [docs/api.md](/c:/Users/sarthak.joshi/Automation/PLP/docs/api.md)
- Database schema: [sql/schema.sql](/c:/Users/sarthak.joshi/Automation/PLP/sql/schema.sql)
- Deployment guide: [docs/deployment.md](/c:/Users/sarthak.joshi/Automation/PLP/docs/deployment.md)
- Auth0 guide: [docs/auth0-integration.md](/c:/Users/sarthak.joshi/Automation/PLP/docs/auth0-integration.md)
- Evaluation prompt template: [templates/evaluation_prompt.txt](/c:/Users/sarthak.joshi/Automation/PLP/templates/evaluation_prompt.txt)
