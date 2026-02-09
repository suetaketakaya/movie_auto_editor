"""Unit tests for ProjectService bug fixes."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.src.application.project_service import ProjectService
from backend.src.core.entities.content_type import ContentType
from backend.src.core.entities.project import Project, ProjectStatus


class TestProjectServiceSyncTaskQueue:
    """Verify start_processing and cancel_project work with sync task queue."""

    @pytest.fixture
    def sync_task_queue(self):
        """Task queue with sync enqueue/cancel (matching TaskQueuePort)."""
        mock = MagicMock()
        mock.enqueue.return_value = "task-abc-123"
        mock.cancel.return_value = True
        return mock

    @pytest.fixture
    def service(self, mock_project_repository, mock_file_storage, sync_task_queue):
        return ProjectService(
            repository=mock_project_repository,
            file_storage=mock_file_storage,
            task_queue=sync_task_queue,
        )

    @pytest.mark.asyncio
    async def test_start_processing_no_type_error(
        self, service, mock_project_repository, sync_task_queue
    ):
        """start_processing must not raise TypeError from awaiting sync enqueue."""
        project = Project(
            id="proj-1",
            name="Test",
            input_video_path="/tmp/input.mp4",
            output_dir="/tmp/output",
            content_type=ContentType.GENERAL,
        )
        mock_project_repository.get_by_id.return_value = project

        task_id = await service.start_processing("proj-1")

        assert task_id == "task-abc-123"
        sync_task_queue.enqueue.assert_called_once_with(
            "process_video", {"project_id": "proj-1"}
        )

    @pytest.mark.asyncio
    async def test_cancel_project_no_type_error(
        self, service, mock_project_repository, sync_task_queue
    ):
        """cancel_project must not raise TypeError from awaiting sync cancel."""
        project = Project(
            id="proj-1",
            name="Test",
            input_video_path="/tmp/input.mp4",
            output_dir="/tmp/output",
            content_type=ContentType.GENERAL,
        )
        project.metadata["task_id"] = "task-abc-123"
        mock_project_repository.get_by_id.return_value = project

        await service.cancel_project("proj-1")

        sync_task_queue.cancel.assert_called_once_with("task-abc-123")
