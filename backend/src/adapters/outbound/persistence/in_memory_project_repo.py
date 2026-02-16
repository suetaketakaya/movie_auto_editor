"""In-memory implementation of ProjectRepositoryPort for backward compatibility."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from backend.src.core.entities.project import Project, ProjectStatus

logger = logging.getLogger(__name__)


class InMemoryProjectRepository:
    """Thread-safe in-memory project store.

    Replaces the legacy ``active_jobs`` dict while conforming to
    :class:`ProjectRepositoryPort`.
    """

    def __init__(self) -> None:
        self._store: dict[str, Project] = {}
        self._lock = asyncio.Lock()

    # -- ProjectRepositoryPort implementation ----------------------------------

    async def save(self, project: Project) -> Project:
        """Persist (or overwrite) a project in the in-memory store."""
        async with self._lock:
            project.updated_at = datetime.utcnow()
            self._store[project.id] = project
            logger.debug("Saved project %s", project.id)
            return project

    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """Retrieve a project by its identifier."""
        async with self._lock:
            project = self._store.get(project_id)
            if project is None:
                logger.debug("Project %s not found", project_id)
            return project

    async def list_all(self) -> list[Project]:
        """Return every stored project."""
        async with self._lock:
            return list(self._store.values())

    async def list_by_user(self, user_id: str) -> list[Project]:
        """Return projects owned by a specific user."""
        async with self._lock:
            return [p for p in self._store.values() if p.user_id == user_id]

    async def delete(self, project_id: str) -> None:
        """Remove a project from the store."""
        async with self._lock:
            removed = self._store.pop(project_id, None)
            if removed is None:
                logger.warning("Attempted to delete non-existent project %s", project_id)
            else:
                logger.debug("Deleted project %s", project_id)

    async def update_status(
        self, project_id: str, status: str, progress: int = 0
    ) -> None:
        """Update status and progress for an existing project."""
        async with self._lock:
            project = self._store.get(project_id)
            if project is None:
                logger.warning(
                    "Cannot update status: project %s not found", project_id
                )
                return
            project.status = ProjectStatus(status)
            project.progress = progress
            project.updated_at = datetime.utcnow()
            logger.debug(
                "Updated project %s status=%s progress=%d",
                project_id,
                status,
                progress,
            )
