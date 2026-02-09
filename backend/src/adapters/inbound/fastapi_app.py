"""
FastAPI application - primary inbound adapter.
Replaces legacy app.py monolith.
"""
from __future__ import annotations

import logging
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging(settings.logging.level)
    logger.info("ClipMontage backend starting up...")
    from backend.src.infrastructure.container import ApplicationContainer
    app.state.container = ApplicationContainer(settings)
    yield
    logger.info("ClipMontage backend shutting down...")


app = FastAPI(
    title="ClipMontage API",
    description="Universal Video Montage Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log each request with method, path, status, and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


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
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/plugins")
async def list_plugins():
    from backend.src.application.plugins.plugin_registry import PluginRegistry
    registry = PluginRegistry.create_default()
    return {"plugins": registry.list_plugins()}


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time project updates."""
    notifier = app.state.container.notification()
    await notifier.connect(project_id, websocket)
    try:
        while True:
            # Keep connection alive, waiting for messages
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
