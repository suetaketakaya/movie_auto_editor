"""Integration tests for health endpoint."""
from __future__ import annotations

import pytest


class TestHealthEndpoint:
    """Tests for /api/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, async_client):
        response = await async_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_returns_version(self, async_client):
        response = await async_client.get("/api/health")

        data = response.json()
        assert data["version"] == "0.2.0"
