"""Integration tests for GCS chunked upload endpoints."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("APP_ENV", "test")
os.environ["FIREBASE_ENABLED"] = "false"

from backend.src.adapters.inbound.fastapi_app import app
from backend.src.infrastructure.config import Settings
from backend.src.infrastructure.container import ApplicationContainer


def _make_mock_gcs_storage():
    """Create a mock GCSFileStorage-like object."""
    mock = MagicMock()
    mock.create_resumable_upload_session.return_value = "https://storage.googleapis.com/upload/session123"
    mock.gcs_object_exists.return_value = True
    # FileStoragePort methods
    mock.get_file_path.return_value = "/tmp/test.mp4"
    mock.list_files.return_value = []
    return mock


@pytest.fixture
def gcs_settings():
    """Settings with GCS enabled."""
    settings = Settings()
    settings.persistence_backend = "memory"
    settings.app_env = "test"
    settings.firebase.enabled = False
    settings.gcs.enabled = True
    settings.gcs.bucket_name = "test-bucket"
    return settings


@pytest.fixture
def gcs_container(gcs_settings):
    """Container with mocked GCS file storage."""
    container = ApplicationContainer(gcs_settings)
    mock_storage = _make_mock_gcs_storage()
    container._cache["file_storage"] = mock_storage
    return container


@pytest.fixture
async def gcs_client(gcs_container):
    """Async test client with GCS enabled."""
    app.state.container = gcs_container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestInitiateGCSUpload:
    @pytest.mark.asyncio
    async def test_returns_503_when_gcs_disabled(self, async_client):
        """Should return 503 when GCS is not configured."""
        response = await async_client.post(
            "/api/processing/upload/initiate",
            json={"filename": "video.mp4", "name": "Test"},
        )
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_rejects_invalid_extension(self, gcs_client):
        """Should reject non-video files."""
        response = await gcs_client.post(
            "/api/processing/upload/initiate",
            json={"filename": "document.txt", "name": "Test"},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_upload_url(self, gcs_client):
        """Should return project_id, upload_url, and gcs_object_name."""
        response = await gcs_client.post(
            "/api/processing/upload/initiate",
            json={"filename": "gameplay.mp4", "name": "My Game"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert "upload_url" in data
        assert data["upload_url"].startswith("https://")
        assert "gcs_object_name" in data
        assert data["gcs_object_name"].startswith("uploads/")

    @pytest.mark.asyncio
    async def test_sanitizes_filename(self, gcs_client):
        """Should sanitize dangerous filenames."""
        response = await gcs_client.post(
            "/api/processing/upload/initiate",
            json={"filename": "../../../etc/passwd.mp4", "name": "Test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert ".." not in data["gcs_object_name"]


class TestCompleteGCSUpload:
    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_project(self, gcs_client):
        response = await gcs_client.post(
            "/api/processing/upload/complete",
            json={"project_id": "nonexistent", "gcs_object_name": "uploads/x/video.mp4"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_when_object_missing(self, gcs_client, gcs_container):
        """Should return 400 when GCS object doesn't exist."""
        # Initiate to create a project
        init_resp = await gcs_client.post(
            "/api/processing/upload/initiate",
            json={"filename": "video.mp4", "name": "Test"},
        )
        project_id = init_resp.json()["project_id"]

        # Make mock report object as missing
        gcs_container._cache["file_storage"].gcs_object_exists.return_value = False

        response = await gcs_client.post(
            "/api/processing/upload/complete",
            json={"project_id": project_id, "gcs_object_name": "uploads/fake/video.mp4"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_succeeds_when_object_exists(self, gcs_client, gcs_container):
        """Should succeed when GCS object exists."""
        # Initiate
        init_resp = await gcs_client.post(
            "/api/processing/upload/initiate",
            json={"filename": "video.mp4", "name": "Test"},
        )
        data = init_resp.json()

        # Ensure mock reports object exists
        gcs_container._cache["file_storage"].gcs_object_exists.return_value = True

        response = await gcs_client.post(
            "/api/processing/upload/complete",
            json={
                "project_id": data["project_id"],
                "gcs_object_name": data["gcs_object_name"],
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "upload_complete"
