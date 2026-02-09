"""
Dashboard API routes for frontend consumption.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(request: Request):
    """Get overall dashboard statistics."""
    container = request.app.state.container
    project_service = container.project_service()
    projects = await project_service.list_projects()

    completed = [p for p in projects if p.status.value == "completed"]
    processing = [p for p in projects if p.status.value == "processing"]
    failed = [p for p in projects if p.status.value == "failed"]

    return {
        "total_projects": len(projects),
        "completed": len(completed),
        "processing": len(processing),
        "failed": len(failed),
        "recent_projects": [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status.value,
                "progress": p.progress,
                "created_at": p.created_at.isoformat(),
            }
            for p in sorted(projects, key=lambda x: x.created_at, reverse=True)[:10]
        ],
    }
