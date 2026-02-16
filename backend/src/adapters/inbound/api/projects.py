"""
Project management API routes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from backend.src.adapters.inbound.api.dependencies import get_current_user
from backend.src.core.entities.user import User

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
    user_id: Optional[str] = None
    error_message: Optional[str] = None


def _get_project_service(request: Request):
    return request.app.state.container.project_service()


@router.post("", response_model=ProjectResponse)
async def create_project(
    body: CreateProjectRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    service = _get_project_service(request)
    project = await service.create_project(
        name=body.name,
        input_video_path="",
        output_dir="",
        content_type=body.content_type,
        config=body.config,
    )
    project.user_id = user.id
    repo = request.app.state.container.project_repository()
    await repo.save(project)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        status=project.status.value,
        progress=project.progress,
        content_type=project.content_type.value,
        created_at=project.created_at.isoformat(),
        user_id=project.user_id,
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    request: Request,
    user: User = Depends(get_current_user),
):
    service = _get_project_service(request)
    repo = request.app.state.container.project_repository()

    # Try user-scoped listing first, fall back to list_all + filter
    if hasattr(repo, "list_by_user"):
        projects = await repo.list_by_user(user.id)
    else:
        all_projects = await service.list_projects()
        projects = [p for p in all_projects if p.user_id == user.id or p.user_id is None]

    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            status=p.status.value,
            progress=p.progress,
            content_type=p.content_type.value,
            created_at=p.created_at.isoformat(),
            user_id=p.user_id,
            error_message=p.error_message,
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    service = _get_project_service(request)
    project = await service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    # Ownership check (allow if user_id is None for legacy projects)
    if project.user_id and project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return ProjectResponse(
        id=project.id,
        name=project.name,
        status=project.status.value,
        progress=project.progress,
        content_type=project.content_type.value,
        created_at=project.created_at.isoformat(),
        user_id=project.user_id,
        error_message=project.error_message,
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    service = _get_project_service(request)
    project = await service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id and project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    await service.delete_project(project_id)
    return {"status": "deleted"}


@router.post("/{project_id}/cancel")
async def cancel_project(
    project_id: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    service = _get_project_service(request)
    project = await service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id and project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        await service.cancel_project(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "cancelled"}
