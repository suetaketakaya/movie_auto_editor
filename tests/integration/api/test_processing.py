"""Integration tests for processing API."""
from __future__ import annotations

import pytest


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

        assert response.status_code == 400

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
