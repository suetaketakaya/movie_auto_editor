"""Integration tests for dashboard API."""
from __future__ import annotations

import asyncio
import pytest


class TestDashboardAPI:
    """Tests for /api/dashboard endpoints."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, async_client):
        response = await async_client.get("/api/dashboard/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_projects" in data
        assert "completed" in data
        assert "processing" in data
        assert "failed" in data
        assert "recent_projects" in data
        assert isinstance(data["recent_projects"], list)

    @pytest.mark.asyncio
    async def test_get_stats_with_projects(self, async_client):
        # Create some projects
        await async_client.post(
            "/api/projects",
            json={"name": "Project 1", "content_type": "general"},
        )
        await async_client.post(
            "/api/projects",
            json={"name": "Project 2", "content_type": "fps_montage"},
        )

        response = await async_client.get("/api/dashboard/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_projects"] >= 2
        assert len(data["recent_projects"]) >= 2

    @pytest.mark.asyncio
    async def test_recent_projects_sorted_by_date(self, async_client):
        # Create projects with small delay to ensure different timestamps
        await async_client.post(
            "/api/projects",
            json={"name": "First", "content_type": "general"},
        )
        await asyncio.sleep(0.01)  # Ensure different timestamps
        await async_client.post(
            "/api/projects",
            json={"name": "Second", "content_type": "general"},
        )

        response = await async_client.get("/api/dashboard/stats")

        data = response.json()
        recent = data["recent_projects"]
        if len(recent) >= 2:
            # Most recent should be first
            assert recent[0]["name"] == "Second"
