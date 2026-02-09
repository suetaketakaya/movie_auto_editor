"""
Project management use case.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from backend.src.core.entities.content_type import ContentType
from backend.src.core.entities.project import Project, ProjectStatus

logger = logging.getLogger(__name__)


class ProjectService:
    """Manages project lifecycle: create, query, cancel, delete."""

    def __init__(self, repository, file_storage, task_queue):
        self._repository = repository
        self._file_storage = file_storage
        self._task_queue = task_queue

    async def create_project(
        self,
        name: str,
        input_video_path: str,
        output_dir: str,
        content_type: str = "general",
        config: Optional[dict] = None,
    ) -> Project:
        project = Project(
            id=str(uuid.uuid4()),
            name=name,
            input_video_path=input_video_path,
            output_dir=output_dir,
            content_type=ContentType(content_type),
            config=config or {},
        )
        await self._repository.save(project)
        logger.info("Project created: %s (%s)", project.id, name)
        return project

    async def start_processing(self, project_id: str) -> str:
        """Enqueue the project for processing. Returns task ID."""
        project = await self._repository.get_by_id(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        if project.status != ProjectStatus.UPLOADED:
            raise ValueError(f"Project {project_id} is in state {project.status.value}, cannot start")

        task_id = self._task_queue.enqueue(
            "process_video", {"project_id": project_id}
        )
        project.start_processing()
        project.metadata["task_id"] = task_id
        await self._repository.save(project)
        return task_id

    async def get_project(self, project_id: str) -> Optional[Project]:
        return await self._repository.get_by_id(project_id)

    async def list_projects(self) -> list[Project]:
        return await self._repository.list_all()

    async def cancel_project(self, project_id: str) -> None:
        project = await self._repository.get_by_id(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        task_id = project.metadata.get("task_id")
        if task_id:
            self._task_queue.cancel(task_id)
        project.cancel()
        await self._repository.save(project)

    async def delete_project(self, project_id: str) -> None:
        project = await self._repository.get_by_id(project_id)
        if project is None:
            return
        await self._repository.delete(project_id)
        logger.info("Project deleted: %s", project_id)
