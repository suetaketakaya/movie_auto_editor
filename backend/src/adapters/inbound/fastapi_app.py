"""
FastAPI application - primary inbound adapter.
Replaces legacy app.py monolith.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from backend.src.infrastructure.config import Settings
from backend.src.infrastructure.logging_config import setup_logging

logger = logging.getLogger(__name__)

settings = Settings()

# Project root for static files
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

# Auth-exempt paths (no Bearer token needed)
_AUTH_EXEMPT_PREFIXES = (
    "/api/health", "/api/config/firebase",
    "/static", "/media", "/ws/",
    "/docs", "/openapi.json", "/redoc",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging(settings.logging.level)
    settings.validate_production()
    logger.info("ClipMontage backend starting up...")
    from backend.src.infrastructure.container import ApplicationContainer
    app.state.container = ApplicationContainer(settings)
    yield
    logger.info("ClipMontage backend shutting down...")


app = FastAPI(
    title="ClipMontage API",
    description="Universal Video Montage Platform",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS: restrict origins in production
_allowed_origin = os.environ.get("ALLOWED_ORIGIN", "")
if settings.app_env == "production" and _allowed_origin:
    _origins = [o.strip() for o in _allowed_origin.split(",") if o.strip()]
else:
    _origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Key authentication (legacy fallback)
_api_key = os.environ.get("API_KEY", "")


def _cors_headers(request: Request) -> dict:
    """Build CORS headers for early-return responses from auth middleware.

    When the middleware short-circuits (returns without call_next), the
    response bypasses CORSMiddleware.  We must add CORS headers manually
    so the browser can read the JSON error body instead of seeing an
    opaque CORS failure.
    """
    origin = request.headers.get("origin", "")
    if not origin:
        return {}
    # Mirror the CORSMiddleware config: allow any origin (dev) or the
    # configured allow-list (production).
    if _origins == ["*"] or origin in _origins:
        return {
            "access-control-allow-origin": origin,
            "access-control-allow-credentials": "true",
            "vary": "Origin",
        }
    return {}


def _auth_error(request: Request, detail: str) -> JSONResponse:
    """Return a 401 with CORS headers so the browser can read the body."""
    headers = _cors_headers(request)
    headers["cache-control"] = "no-store, no-cache, must-revalidate"
    return JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers=headers,
    )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Authenticate via Firebase Bearer token or legacy API key.

    Attaches ``request.state.user`` when authentication succeeds.
    """
    path = request.url.path

    # Skip auth for CORS preflight, exempt paths, and the root page
    if request.method == "OPTIONS":
        return await call_next(request)
    if path == "/" or any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
        return await call_next(request)

    # --- Try Bearer token (Firebase) first ---
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        logger.info("Auth: Bearer token received for %s (len=%d)", path, len(token))
        try:
            user_auth = request.app.state.container.user_auth()
            user = await user_auth.verify_token(token)
        except Exception as exc:
            logger.warning("Bearer token verification failed: %s", exc)
            return _auth_error(request, "Invalid or expired token")
        if not user:
            logger.warning("Auth: verify_token returned None for %s", path)
            return _auth_error(request, "Invalid or expired token")
        logger.info("Auth: token verified OK for user=%s", user.email)
        request.state.user = user
        return await call_next(request)

    # --- Fallback: API Key ---
    if _api_key:
        provided_key = request.headers.get("X-API-Key", "")
        if provided_key == _api_key:
            # API-key users get a pseudo-user
            from backend.src.core.entities.user import User
            request.state.user = User(
                id="apikey-user",
                firebase_uid="apikey-user",
                email="apikey@system",
                display_name="API Key User",
            )
            return await call_next(request)
        return _auth_error(request, "Invalid or missing API key")

    # --- No auth configured (dev mode) — attach dev user ---
    if not settings.firebase.enabled:
        try:
            user_auth = request.app.state.container.user_auth()
            user = await user_auth.verify_token("")
            if user:
                request.state.user = user
        except Exception:
            pass
        return await call_next(request)

    return _auth_error(request, "Authentication required")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log each request with method, path, status, and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    # Prevent Cloudflare/browser from caching API responses
    if request.url.path.startswith("/api"):
        response.headers["cache-control"] = "no-store, no-cache, must-revalidate"
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


from backend.src.core.exceptions import (
    ClipMontageError,
    ProjectNotFoundError,
    ProcessingError,
    UploadValidationError,
    AIAnalysisError,
    FFmpegError,
)


@app.exception_handler(ProjectNotFoundError)
async def project_not_found_handler(request: Request, exc: ProjectNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(UploadValidationError)
async def upload_validation_handler(request: Request, exc: UploadValidationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ProcessingError)
async def processing_error_handler(request: Request, exc: ProcessingError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(AIAnalysisError)
async def ai_analysis_handler(request: Request, exc: AIAnalysisError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(FFmpegError)
async def ffmpeg_error_handler(request: Request, exc: FFmpegError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── API routes ─────────────────────────────────────────────────

from backend.src.adapters.inbound.api.projects import router as projects_router
from backend.src.adapters.inbound.api.processing import router as processing_router
from backend.src.adapters.inbound.api.experiments import router as experiments_router
from backend.src.adapters.inbound.api.dashboard import router as dashboard_router

app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(processing_router, prefix="/api/processing", tags=["processing"])
app.include_router(experiments_router, prefix="/api/experiments", tags=["experiments"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "vision_backend": settings.vision_backend,
    }


@app.get("/api/config/firebase")
async def firebase_config():
    """Return public Firebase config for frontend SDK initialization."""
    return {
        "enabled": settings.firebase.enabled,
        "apiKey": settings.firebase.api_key,
        "authDomain": settings.firebase.auth_domain,
        "projectId": settings.firebase.project_id,
    }


@app.get("/api/plugins")
async def list_plugins():
    from backend.src.application.plugins.plugin_registry import PluginRegistry
    registry = PluginRegistry.create_default()
    return {"plugins": registry.list_plugins()}


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str, token: str = ""):
    """WebSocket endpoint for real-time project updates.

    Accepts an optional ``token`` query parameter for Firebase auth.
    """
    # Verify token if Firebase is enabled
    if settings.firebase.enabled and token:
        user_auth = app.state.container.user_auth()
        user = await user_auth.verify_token(token)
        if not user:
            await websocket.close(code=4001, reason="Invalid token")
            return

    notifier = app.state.container.notification()
    await notifier.connect(project_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await notifier.disconnect(project_id, websocket)


@app.get("/api/download/{project_id}")
async def download_video(project_id: str):
    """Download the processed video for a project."""
    project_service = app.state.container.project_service()
    project = await project_service.get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    output_paths = project.output_paths or {}
    main_video = output_paths.get("main")

    if not main_video:
        raise HTTPException(status_code=404, detail="Output video not found")

    video_path = Path(main_video)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"{project.name}_highlight.mp4",
    )


@app.post("/api/projects/{project_id}/cancel")
async def cancel_processing(project_id: str):
    """Cancel processing for a project."""
    project_service = app.state.container.project_service()
    project = await project_service.get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    project.fail("Cancelled by user")
    repo = app.state.container.project_repository()
    await repo.save(project)
    notifier = app.state.container.notification()
    await notifier.send_error(project_id, "Processing cancelled by user")

    return {"status": "cancelled", "project_id": project_id}


# ── Static files & Frontend ─────────────────────────────────────

# Serve static assets (CSS, JS)
static_dir = PROJECT_ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Serve media files
media_dir = Path(settings.storage.media_root)
if media_dir.exists():
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend page."""
    index_path = PROJECT_ROOT / "templates" / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>ClipMontage API</h1><p>Frontend not found.</p>")
