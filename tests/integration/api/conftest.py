"""Integration test fixtures for API testing."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from backend.src.adapters.inbound.fastapi_app import app
from backend.src.infrastructure.config import Settings
from backend.src.infrastructure.container import ApplicationContainer


@pytest.fixture
def test_settings():
    """Create test settings with in-memory backends."""
    settings = Settings()
    settings.persistence_backend = "memory"
    settings.app_env = "test"
    return settings


@pytest.fixture
def test_container(test_settings):
    """Create a test container with mocked dependencies."""
    return ApplicationContainer(test_settings)


@pytest.fixture
async def async_client(test_container):
    """Create an async test client for the FastAPI app."""
    app.state.container = test_container

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
