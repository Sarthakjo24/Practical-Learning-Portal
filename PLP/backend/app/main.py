from __future__ import annotations

from __future__ import annotations

import asyncio
from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import admin, auth, candidate, evaluation, modules
from app.core.config import settings
from app.core.database import init_database
from app.initial_data import seed_default_data
from app.services.processing_service import (
    enqueue_pending_processing_sessions,
    run_processing_requeue_loop,
)


limiter = Limiter(key_func=get_remote_address, default_limits=[settings.api_rate_limit])


def _frontend_asset_response(frontend_dist: Path, requested_path: str) -> FileResponse | None:
    cleaned = requested_path.strip("/")
    if not cleaned:
        index_file = frontend_dist / "index.html"
        return FileResponse(index_file) if index_file.exists() else None

    candidate = (frontend_dist / cleaned).resolve()
    if candidate.is_file() and str(candidate).startswith(str(frontend_dist.resolve())):
        return FileResponse(candidate)
    return None


def create_app() -> FastAPI:
    settings.ensure_directories()

    app = FastAPI(
        title=settings.project_name,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/storage", StaticFiles(directory=settings.storage_dir), name="storage")
    app.mount("/assets/questions", StaticFiles(directory=settings.question_audio_dir), name="question-audios")

    app.include_router(modules.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(candidate.router, prefix=settings.api_v1_prefix)
    app.include_router(admin.router, prefix=settings.api_v1_prefix)
    app.include_router(evaluation.router, prefix=settings.api_v1_prefix)

    frontend_dist = settings.frontend_dist_dir
    index_file = frontend_dist / "index.html"
    if index_file.exists():

        @app.get("/", include_in_schema=False)
        async def serve_frontend_root() -> FileResponse:
            return FileResponse(index_file)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend_app(full_path: str) -> FileResponse:
            excluded_prefixes = (
                settings.api_v1_prefix.strip("/") + "/",
                "docs",
                "redoc",
                "openapi.json",
                "storage/",
                "assets/questions/",
            )
            if full_path in {"docs", "redoc", "openapi.json"} or full_path.startswith(excluded_prefixes):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

            asset_response = _frontend_asset_response(frontend_dist, full_path)
            if asset_response is not None:
                return asset_response
            return FileResponse(index_file)

    @app.on_event("startup")
    async def _initialize_database() -> None:
        await init_database()
        await seed_default_data()
        pending_count = await enqueue_pending_processing_sessions()
        if pending_count:
            logging.getLogger(__name__).info(
                "Requeued %d pending transcription/evaluation sessions on startup.", pending_count
            )

        app.state.processing_requeue_task = asyncio.create_task(run_processing_requeue_loop())

    @app.on_event("shutdown")
    async def _shutdown_requeue_loop() -> None:
        task = getattr(app.state, "processing_requeue_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return app


app = create_app()
