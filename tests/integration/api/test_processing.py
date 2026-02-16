"""Integration tests for processing API."""
from __future__ import annotations

import pytest

from backend.src.core.exceptions import (
    ProjectNotFoundError,
    UploadValidationError,
    ProcessingError,
    AIAnalysisError,
    FFmpegError,
)


class TestProcessingAPI:
    """Tests for /api/processing endpoints."""

    @pytest.mark.asyncio
    async def test_start_processing_not_found(self, async_client):
        response = await async_client.post(
            "/api/processing/start",
            json={
                "project_id": "nonexistent-id",
                "content_type": "fps_montage",
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, async_client):
        response = await async_client.get("/api/processing/status/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_status_after_create(self, async_client):
        # Create a project first
        create_response = await async_client.post(
            "/api/projects",
            json={"name": "Status Test", "content_type": "general"},
        )
        project_id = create_response.json()["id"]

        response = await async_client.get(f"/api/processing/status/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
        assert data["status"] == "uploaded"
        assert "progress" in data


class TestExceptionHandlers:
    """Tests that custom exceptions map to correct HTTP status codes."""

    @pytest.mark.asyncio
    async def test_project_not_found_returns_404(self, async_client):
        """ProjectNotFoundError should map to 404."""
        response = await async_client.get("/api/download/does-not-exist")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_value_error_returns_400(self, async_client):
        """Start processing with nonexistent project returns 404."""
        response = await async_client.post(
            "/api/processing/start",
            json={"project_id": "invalid", "content_type": "fps_montage"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_health_endpoint_always_accessible(self, async_client):
        """Health endpoint should work without auth."""
        response = await async_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestCancelAPI:
    """Tests for /api/projects/{project_id}/cancel endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, async_client):
        """Cancelling a non-existent project should return 404."""
        response = await async_client.post("/api/projects/nonexistent-id/cancel")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_existing_project(self, async_client):
        """Cancelling an existing project should succeed."""
        create_response = await async_client.post(
            "/api/projects",
            json={"name": "Cancel Test", "content_type": "general"},
        )
        project_id = create_response.json()["id"]

        response = await async_client.post(f"/api/projects/{project_id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
