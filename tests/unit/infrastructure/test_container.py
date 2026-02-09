"""Unit tests for ApplicationContainer wiring."""
from __future__ import annotations

import pytest

from backend.src.infrastructure.config import Settings
from backend.src.infrastructure.container import ApplicationContainer


class TestApplicationContainer:
    """Test that all container accessors return non-None instances."""

    @pytest.fixture
    def container(self) -> ApplicationContainer:
        settings = Settings(
            app_env="development",
            persistence_backend="memory",
        )
        return ApplicationContainer(settings)

    def test_video_editor(self, container: ApplicationContainer):
        assert container.video_editor() is not None

    def test_effects(self, container: ApplicationContainer):
        assert container.effects() is not None

    def test_text_overlay(self, container: ApplicationContainer):
        assert container.text_overlay() is not None

    def test_audio(self, container: ApplicationContainer):
        assert container.audio() is not None

    def test_encoding(self, container: ApplicationContainer):
        assert container.encoding() is not None

    def test_vision(self, container: ApplicationContainer):
        assert container.vision() is not None

    def test_frame_extraction(self, container: ApplicationContainer):
        assert container.frame_extraction() is not None

    def test_project_repository_in_memory(self, container: ApplicationContainer):
        repo = container.project_repository()
        assert repo is not None
        assert "InMemory" in type(repo).__name__

    def test_experiment_repository_in_memory(self, container: ApplicationContainer):
        repo = container.experiment_repository()
        assert repo is not None
        assert "InMemory" in type(repo).__name__

    def test_file_storage(self, container: ApplicationContainer):
        assert container.file_storage() is not None

    def test_task_queue_in_dev(self, container: ApplicationContainer):
        queue = container.task_queue()
        assert queue is not None
        assert "InProcess" in type(queue).__name__

    def test_notification(self, container: ApplicationContainer):
        assert container.notification() is not None

    def test_metrics_store_file_backend(self, container: ApplicationContainer):
        store = container.metrics_store()
        assert store is not None
        assert "File" in type(store).__name__

    def test_llm_reasoning(self, container: ApplicationContainer):
        assert container.llm_reasoning() is not None

    def test_thumbnail(self, container: ApplicationContainer):
        assert container.thumbnail() is not None

    def test_youtube_api(self, container: ApplicationContainer):
        assert container.youtube_api() is not None

    def test_process_video_service(self, container: ApplicationContainer):
        assert container.process_video_service() is not None

    def test_project_service(self, container: ApplicationContainer):
        assert container.project_service() is not None

    def test_experiment_service(self, container: ApplicationContainer):
        assert container.experiment_service() is not None

    def test_caching(self, container: ApplicationContainer):
        """Verify that the same instance is returned on repeated calls."""
        repo1 = container.project_repository()
        repo2 = container.project_repository()
        assert repo1 is repo2
