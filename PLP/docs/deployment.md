# Deployment Guide

## Local

1. Copy [backend/.env.example](/c:/Users/sarthak.joshi/Automation/PLP/backend/.env.example) to `backend/.env`.
2. Apply [sql/schema.sql](/c:/Users/sarthak.joshi/Automation/PLP/sql/schema.sql) to MySQL or MariaDB.
3. Install backend dependencies from [backend/requirements.txt](/c:/Users/sarthak.joshi/Automation/PLP/backend/requirements.txt).
4. Install frontend dependencies from [frontend/package.json](/c:/Users/sarthak.joshi/Automation/PLP/frontend/package.json).
5. Run FastAPI with Uvicorn.
6. Run Celery with Redis.
7. Run the React frontend with Vite.

## Production

- React static build behind Nginx or CDN
- FastAPI behind Gunicorn + Uvicorn workers
- Dedicated Celery workers for assessment jobs
- Redis for queueing
- MySQL/MariaDB with backups
- Object storage replacing local disk when horizontally scaling

## Scaling Guidance

- Start with 2-4 Gunicorn workers for 50-100 concurrent users.
- Use 2+ Celery workers and separate evaluation/transcription queues if volume rises.
- Move recordings from local disk to S3-compatible storage before multi-instance deployment.
- Use a GPU-backed or dedicated transcription host if Faster Whisper becomes the bottleneck.
