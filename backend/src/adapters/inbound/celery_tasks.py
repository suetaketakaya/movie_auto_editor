"""
Celery task definitions.
"""
from __future__ import annotations

import asyncio
import logging

from celery import Celery

from backend.src.infrastructure.config import Settings

logger = logging.getLogger(__name__)

settings = Settings()

celery_app = Celery(
    "clipmontage",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, name="process_video")
def process_video_task(self, project_id: str):
    """Celery task wrapper for video processing."""
    logger.info("Starting Celery task for project: %s", project_id)
    from backend.src.infrastructure.container import ApplicationContainer
    from backend.src.application.dto.process_request import ProcessRequest
    from backend.src.core.entities.content_type import ContentType

    container = ApplicationContainer(settings)
    project_service = container.project_service()

    # Get project info
    project = asyncio.get_event_loop().run_until_complete(
        project_service.get_project(project_id)
    )
    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    request = ProcessRequest(
        project_id=project.id,
        project_name=project.name,
        input_video_path=project.input_video_path,
        output_dir=project.output_dir,
        content_type=project.content_type,
        config=project.config,
    )

    service = container.process_video_service()
    result = asyncio.get_event_loop().run_until_complete(service.execute(request))

    logger.info("Celery task completed for project: %s", project_id)
    return result.to_dict()
