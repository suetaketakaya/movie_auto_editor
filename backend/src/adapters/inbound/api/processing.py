"""
Video processing API routes.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from backend.src.adapters.inbound.api.dependencies import get_current_user
from backend.src.core.entities.user import User

router = APIRouter()

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB


class ProcessRequest(BaseModel):
    project_id: str
    content_type: str = "fps_montage"
    config: Optional[dict] = None


class ProcessResponse(BaseModel):
    task_id: str
    project_id: str
    status: str


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and invalid characters."""
    # Take only the basename (strip any directory components)
    filename = os.path.basename(filename)
    # Remove any null bytes
    filename = filename.replace("\x00", "")
    # Replace potentially dangerous characters
    filename = re.sub(r'[^\w\s\-.]', '_', filename)
    # Collapse multiple dots/underscores
    filename = re.sub(r'\.{2,}', '.', filename)
    filename = re.sub(r'_{2,}', '_', filename)
    if not filename or filename.startswith('.'):
        filename = "upload" + filename
    return filename


def _validate_extension(filename: str) -> str:
    """Validate file extension and return it. Raises HTTPException if invalid."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return ext


@router.post("/upload")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
    content_type: str = Form("fps_montage"),
    user: User = Depends(get_current_user),
):
    """Upload a video file and create a project."""
    container = request.app.state.container
    settings = container.settings

    # Validate file extension
    original_name = file.filename or "upload.mp4"
    _validate_extension(original_name)

    # Validate file size from Content-Length header (early rejection)
    max_size_bytes = settings.web.max_upload_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.web.max_upload_size_mb}MB",
        )

    # Sanitize filename
    safe_filename = _sanitize_filename(original_name)

    project_id = str(uuid.uuid4())
    output_dir = Path(settings.storage.media_root) / project_id
    output_dir.mkdir(parents=True, exist_ok=True)

    video_path = output_dir / safe_filename

    # Stream file in chunks instead of reading all into memory
    total_written = 0
    try:
        with open(video_path, "wb") as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {settings.web.max_upload_size_mb}MB",
                    )
                f.write(chunk)
    except HTTPException:
        # Clean up partial file on validation failure
        if video_path.exists():
            video_path.unlink()
        raise

    project_service = container.project_service()
    project = await project_service.create_project(
        name=name or original_name,
        input_video_path=str(video_path),
        output_dir=str(output_dir),
        content_type=content_type,
    )
    # Assign project to authenticated user
    project.user_id = user.id
    repo = container.project_repository()
    await repo.save(project)

    return {"project_id": project.id, "video_path": str(video_path)}


class InitiateUploadRequest(BaseModel):
    filename: str
    content_type: str = "video/mp4"
    name: str = ""
    upload_content_type: str = "fps_montage"


class InitiateUploadResponse(BaseModel):
    project_id: str
    upload_url: str
    gcs_object_name: str


class CompleteUploadRequest(BaseModel):
    project_id: str
    gcs_object_name: str


@router.post("/upload/initiate", response_model=InitiateUploadResponse)
async def initiate_gcs_upload(
    body: InitiateUploadRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Step 1 of GCS upload: create project and return a resumable upload session URI."""
    container = request.app.state.container
    settings = container.settings

    if not settings.gcs.enabled:
        raise HTTPException(status_code=503, detail="GCS upload is not configured on this server")

    _validate_extension(body.filename)
    safe_filename = _sanitize_filename(body.filename)

    project_id = str(uuid.uuid4())
    gcs_object_name = f"{settings.gcs.upload_prefix}{project_id}/{safe_filename}"

    file_storage = container.file_storage()
    if not hasattr(file_storage, "create_resumable_upload_session"):
        raise HTTPException(status_code=503, detail="Storage backend does not support GCS uploads")

    upload_url = file_storage.create_resumable_upload_session(
        gcs_object_name, content_type=body.content_type
    )

    output_dir = str(Path(settings.storage.media_root) / project_id)
    gcs_uri = f"gs://{settings.gcs.bucket_name}/{gcs_object_name}"

    project_service = container.project_service()
    project = await project_service.create_project(
        name=body.name or body.filename,
        input_video_path=gcs_uri,
        output_dir=output_dir,
        content_type=body.upload_content_type,
    )
    project.user_id = user.id
    project.metadata["gcs_object_name"] = gcs_object_name
    project.metadata["upload_complete"] = False
    repo = container.project_repository()
    await repo.save(project)

    return InitiateUploadResponse(
        project_id=project.id,
        upload_url=upload_url,
        gcs_object_name=gcs_object_name,
    )


@router.post("/upload/complete")
async def complete_gcs_upload(
    body: CompleteUploadRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Step 2 of GCS upload: verify object exists and mark upload as complete."""
    container = request.app.state.container
    project_service = container.project_service()

    project = await project_service.get_project(body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id and project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    file_storage = container.file_storage()
    if not hasattr(file_storage, "gcs_object_exists"):
        raise HTTPException(status_code=503, detail="GCS storage not configured")

    if not file_storage.gcs_object_exists(body.gcs_object_name):
        raise HTTPException(
            status_code=400,
            detail="GCS object not found. Upload may not have completed.",
        )

    project.metadata["upload_complete"] = True
    repo = container.project_repository()
    await repo.save(project)

    return {"project_id": project.id, "status": "upload_complete"}


@router.post("/start", response_model=ProcessResponse)
async def start_processing(
    body: ProcessRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Start processing a project."""
    container = request.app.state.container
    project_service = container.project_service()

    # Ownership check
    project = await project_service.get_project(body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id and project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        task_id = await project_service.start_processing(body.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProcessResponse(
        task_id=task_id,
        project_id=body.project_id,
        status="queued",
    )


@router.get("/status/{project_id}")
async def get_processing_status(project_id: str, request: Request):
    """Get processing status for a project."""
    container = request.app.state.container
    project_service = container.project_service()
    project = await project_service.get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "project_id": project.id,
        "status": project.status.value,
        "progress": project.progress,
        "result": project.result,
        "error": project.error_message,
    }
