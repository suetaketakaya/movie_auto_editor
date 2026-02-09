"""PostgreSQL implementation of ProjectRepositoryPort using SQLAlchemy async."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.src.core.entities.content_type import ContentType
from backend.src.core.entities.project import Project, ProjectStatus
from backend.src.infrastructure.database import Base

logger = logging.getLogger(__name__)


class ProjectModel(Base):  # type: ignore[misc]
    """SQLAlchemy model for the ``projects`` table."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True)
    name = Column(String(512), nullable=False, default="")
    filename = Column(String(512), nullable=False, default="")
    upload_path = Column(Text, nullable=False, default="")
    input_video_path = Column(Text, nullable=False, default="")
    output_dir = Column(Text, nullable=False, default="")
    content_type = Column(String(64), nullable=False, default=ContentType.GENERAL.value)
    config = Column(JSON, nullable=False, default=dict)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default=ProjectStatus.UPLOADED.value)
    progress = Column(Integer, nullable=False, default=0)
    current_stage = Column(String(128), nullable=False, default="")
    error = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    output_paths = Column(JSON, nullable=False, default=dict)
    engagement_prediction = Column(JSON, nullable=True)
    chapters = Column(JSON, nullable=False, default=list)
    multi_kills = Column(JSON, nullable=False, default=list)
    clutch_moments = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # -- conversion helpers ----------------------------------------------------

    def to_entity(self) -> Project:
        """Convert this ORM row to a domain :class:`Project` entity."""
        return Project(
            id=self.id,
            name=self.name,
            filename=self.filename,
            upload_path=self.upload_path,
            input_video_path=self.input_video_path,
            output_dir=self.output_dir,
            content_type=ContentType(self.content_type),
            config=self.config or {},
            metadata=self.metadata_ or {},
            status=ProjectStatus(self.status),
            progress=self.progress,
            current_stage=self.current_stage,
            error=self.error,
            error_message=self.error_message,
            result=self.result,
            output_paths=self.output_paths or {},
            engagement_prediction=self.engagement_prediction,
            chapters=self.chapters or [],
            multi_kills=self.multi_kills or [],
            clutch_moments=self.clutch_moments or [],
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, project: Project) -> ProjectModel:
        """Create an ORM instance from a domain :class:`Project` entity."""
        return cls(
            id=project.id,
            name=project.name,
            filename=project.filename,
            upload_path=project.upload_path,
            input_video_path=project.input_video_path,
            output_dir=project.output_dir,
            content_type=project.content_type.value,
            config=project.config,
            metadata_=project.metadata,
            status=project.status.value,
            progress=project.progress,
            current_stage=project.current_stage,
            error=project.error,
            error_message=project.error_message,
            result=project.result,
            output_paths=project.output_paths,
            engagement_prediction=project.engagement_prediction,
            chapters=project.chapters,
            multi_kills=project.multi_kills,
            clutch_moments=project.clutch_moments,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class PostgresProjectRepository:
    """Implements :class:`ProjectRepositoryPort` backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- ProjectRepositoryPort implementation ----------------------------------

    async def save(self, project: Project) -> Project:
        """Insert or update a project row."""
        project.updated_at = datetime.utcnow()
        model = ProjectModel.from_entity(project)
        merged = await self._session.merge(model)
        await self._session.commit()
        logger.debug("Saved project %s to PostgreSQL", project.id)
        return merged.to_entity()

    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """Fetch a single project by primary key."""
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        row = result.scalars().first()
        if row is None:
            logger.debug("Project %s not found in PostgreSQL", project_id)
            return None
        return row.to_entity()

    async def list_all(self) -> list[Project]:
        """Return all projects ordered by creation date descending."""
        result = await self._session.execute(
            select(ProjectModel).order_by(ProjectModel.created_at.desc())
        )
        return [row.to_entity() for row in result.scalars().all()]

    async def delete(self, project_id: str) -> None:
        """Delete a project by its identifier."""
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        row = result.scalars().first()
        if row is None:
            logger.warning("Attempted to delete non-existent project %s", project_id)
            return
        await self._session.delete(row)
        await self._session.commit()
        logger.debug("Deleted project %s from PostgreSQL", project_id)

    async def update_status(
        self, project_id: str, status: str, progress: int = 0
    ) -> None:
        """Update only the status and progress columns."""
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        row = result.scalars().first()
        if row is None:
            logger.warning(
                "Cannot update status: project %s not found in PostgreSQL", project_id
            )
            return
        row.status = status
        row.progress = progress
        row.updated_at = datetime.utcnow()
        await self._session.commit()
        logger.debug(
            "Updated project %s status=%s progress=%d in PostgreSQL",
            project_id,
            status,
            progress,
        )
