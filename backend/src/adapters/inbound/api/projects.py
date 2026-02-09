"""
Project management API routes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    content_type: str = "general"
    config: Optional[dict] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    status: str
    progress: float
    content_type: str
    created_at: str
    error_message: Optional[str] = None


def _get_project_service(request: Request):
    return request.app.state.container.project_service()


@router.post("", response_model=ProjectResponse)
async def create_project(body: CreateProjectRequest, request: Request):
    service = _get_project_service(request)
    project = await service.create_project(
        name=body.name,
        input_video_path="",  # Set after upload
        output_dir="",
        content_type=body.content_type,
        config=body.config,
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        status=project.status.value,
        progress=project.progress,
        content_type=project.content_type.value,
        created_at=project.created_at.isoformat(),
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(request: Request):
    service = _get_project_service(request)
    projects = await service.list_projects()
    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            status=p.status.value,
            progress=p.progress,
            content_type=p.content_type.value,
            created_at=p.created_at.isoformat(),
            error_message=p.error_message,
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, request: Request):
    service = _get_project_service(request)
    project = await service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=project.id,
        name=project.name,
        status=project.status.value,
        progress=project.progress,
        content_type=project.content_type.value,
        created_at=project.created_at.isoformat(),
        error_message=project.error_message,
    )


@router.delete("/{project_id}")
async def delete_project(project_id: str, request: Request):
    service = _get_project_service(request)
    await service.delete_project(project_id)
    return {"status": "deleted"}


@router.post("/{project_id}/cancel")
async def cancel_project(project_id: str, request: Request):
    service = _get_project_service(request)
    try:
        await service.cancel_project(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "cancelled"}
