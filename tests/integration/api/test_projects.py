"""Integration tests for projects API."""
from __future__ import annotations

import pytest


class TestProjectsAPI:
    """Tests for /api/projects endpoints."""

    @pytest.mark.asyncio
    async def test_create_project(self, async_client):
        response = await async_client.post(
            "/api/projects",
            json={
                "name": "Test Project",
                "content_type": "fps_montage",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Project"
        assert "id" in data
        assert data["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, async_client):
        response = await async_client.get("/api/projects")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_projects_with_data(self, async_client):
        # Create a project first
        await async_client.post(
            "/api/projects",
            json={"name": "Project 1", "content_type": "general"},
        )

        response = await async_client.get("/api/projects")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_project(self, async_client):
        # Create a project first
        create_response = await async_client.post(
            "/api/projects",
            json={"name": "Get Test", "content_type": "general"},
        )
        project_id = create_response.json()["id"]

        response = await async_client.get(f"/api/projects/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "Get Test"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, async_client):
        response = await async_client.get("/api/projects/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project(self, async_client):
        # Create a project first
        create_response = await async_client.post(
            "/api/projects",
            json={"name": "Delete Test", "content_type": "general"},
        )
        project_id = create_response.json()["id"]

        response = await async_client.delete(f"/api/projects/{project_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify deleted
        get_response = await async_client.get(f"/api/projects/{project_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_project(self, async_client):
        # Create a project first
        create_response = await async_client.post(
            "/api/projects",
            json={"name": "Cancel Test", "content_type": "general"},
        )
        project_id = create_response.json()["id"]

        response = await async_client.post(f"/api/projects/{project_id}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_project_not_found(self, async_client):
        response = await async_client.post("/api/projects/nonexistent-id/cancel")

        assert response.status_code in [400, 404, 500]  # Depends on implementation
