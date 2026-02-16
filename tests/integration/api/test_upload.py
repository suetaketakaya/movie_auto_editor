"""Integration tests for upload and download endpoints."""
from __future__ import annotations

import io
import pytest


class TestUploadAPI:
    """Tests for /api/processing/upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_invalid_extension(self, async_client):
        """Uploading a .txt file should be rejected."""
        file_content = b"not a video"
        response = await async_client.post(
            "/api/processing/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
            data={"name": "test", "content_type": "fps_montage"},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_invalid_extension_exe(self, async_client):
        """Uploading an .exe file should be rejected."""
        file_content = b"MZ..."
        response = await async_client.post(
            "/api/processing/upload",
            files={"file": ("malware.exe", io.BytesIO(file_content), "application/octet-stream")},
            data={"name": "test", "content_type": "fps_montage"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_valid_mp4(self, async_client, tmp_path):
        """Uploading a valid .mp4 should succeed and return project_id."""
        # Create a small fake mp4 file
        file_content = b"\x00" * 1024  # 1KB fake content
        response = await async_client.post(
            "/api/processing/upload",
            files={"file": ("test_video.mp4", io.BytesIO(file_content), "video/mp4")},
            data={"name": "Test Video", "content_type": "fps_montage"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert "video_path" in data

    @pytest.mark.asyncio
    async def test_upload_valid_webm(self, async_client):
        """WebM extension should be accepted."""
        file_content = b"\x00" * 512
        response = await async_client.post(
            "/api/processing/upload",
            files={"file": ("clip.webm", io.BytesIO(file_content), "video/webm")},
            data={"name": "WebM Test", "content_type": "fps_montage"},
        )
        assert response.status_code == 200
        assert "project_id" in response.json()

    @pytest.mark.asyncio
    async def test_upload_filename_sanitized(self, async_client):
        """Filenames with path traversal should be sanitized."""
        file_content = b"\x00" * 512
        response = await async_client.post(
            "/api/processing/upload",
            files={"file": ("../../../etc/passwd.mp4", io.BytesIO(file_content), "video/mp4")},
            data={"name": "test", "content_type": "fps_montage"},
        )
        assert response.status_code == 200
        data = response.json()
        # The saved path should not contain path traversal
        assert ".." not in data["video_path"]


class TestDownloadAPI:
    """Tests for /api/download/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_download_not_found(self, async_client):
        """Downloading a non-existent project should return 404."""
        response = await async_client.get("/api/download/nonexistent-project-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_no_output(self, async_client):
        """Downloading a project with no output video should return 404."""
        # Create a project first
        create_response = await async_client.post(
            "/api/projects",
            json={"name": "No Output", "content_type": "general"},
        )
        project_id = create_response.json()["id"]

        response = await async_client.get(f"/api/download/{project_id}")
        assert response.status_code == 404
