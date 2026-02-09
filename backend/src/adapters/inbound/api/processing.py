"""
Video processing API routes.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

router = APIRouter()


class ProcessRequest(BaseModel):
    project_id: str
    content_type: str = "fps_montage"
    config: Optional[dict] = None


class ProcessResponse(BaseModel):
    task_id: str
    project_id: str
    status: str


@router.post("/upload")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
    content_type: str = Form("fps_montage"),
):
    """Upload a video file and create a project."""
    container = request.app.state.container
    settings = container.settings

    project_id = str(uuid.uuid4())
    output_dir = Path(settings.storage.media_root) / project_id
    output_dir.mkdir(parents=True, exist_ok=True)

    video_path = output_dir / file.filename
    with open(video_path, "wb") as f:
        content = await file.read()
        f.write(content)

    project_service = container.project_service()
    project = await project_service.create_project(
        name=name or file.filename,
        input_video_path=str(video_path),
        output_dir=str(output_dir),
        content_type=content_type,
    )

    return {"project_id": project.id, "video_path": str(video_path)}


@router.post("/start", response_model=ProcessResponse)
async def start_processing(body: ProcessRequest, request: Request):
    """Start processing a project."""
    container = request.app.state.container
    project_service = container.project_service()

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
