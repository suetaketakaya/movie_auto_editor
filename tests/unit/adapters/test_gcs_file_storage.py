"""Unit tests for GCSFileStorage adapter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_storage(tmp_path):
    """Create a GCSFileStorage with mocked GCS client."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with (
        patch("google.cloud.storage.Client", return_value=mock_client),
        patch("google.oauth2.service_account.Credentials.from_service_account_file"),
    ):
        from backend.src.adapters.outbound.storage.gcs_file_storage import GCSFileStorage

        storage = GCSFileStorage(
            bucket_name="test-bucket",
            upload_prefix="uploads/",
            local_cache_dir=str(tmp_path),
        )
    return storage, mock_bucket


class TestCreateResumableSession:
    def test_returns_upload_url(self, tmp_path):
        storage, bucket = _make_storage(tmp_path)
        blob = MagicMock()
        blob.create_resumable_upload_session.return_value = "https://storage.googleapis.com/session123"
        bucket.blob.return_value = blob

        url = storage.create_resumable_upload_session("uploads/proj/video.mp4")

        bucket.blob.assert_called_once_with("uploads/proj/video.mp4")
        blob.create_resumable_upload_session.assert_called_once_with(
            content_type="video/mp4", size=None
        )
        assert url == "https://storage.googleapis.com/session123"

    def test_custom_content_type(self, tmp_path):
        storage, bucket = _make_storage(tmp_path)
        blob = MagicMock()
        blob.create_resumable_upload_session.return_value = "https://example.com"
        bucket.blob.return_value = blob

        storage.create_resumable_upload_session("uploads/proj/video.webm", content_type="video/webm")

        blob.create_resumable_upload_session.assert_called_once_with(
            content_type="video/webm", size=None
        )


class TestGCSObjectExists:
    def test_exists_true(self, tmp_path):
        storage, bucket = _make_storage(tmp_path)
        blob = MagicMock()
        blob.exists.return_value = True
        bucket.blob.return_value = blob

        assert storage.gcs_object_exists("uploads/proj/video.mp4") is True

    def test_exists_false(self, tmp_path):
        storage, bucket = _make_storage(tmp_path)
        blob = MagicMock()
        blob.exists.return_value = False
        bucket.blob.return_value = blob

        assert storage.gcs_object_exists("uploads/proj/video.mp4") is False


class TestDownloadToLocal:
    @pytest.mark.asyncio
    async def test_downloads_file(self, tmp_path):
        storage, bucket = _make_storage(tmp_path)
        blob = MagicMock()
        bucket.blob.return_value = blob

        result = await storage.download_to_local(
            "uploads/proj/video.mp4",
            str(tmp_path / "video.mp4"),
        )

        blob.download_to_filename.assert_called_once_with(str(tmp_path / "video.mp4"))
        assert result == str(tmp_path / "video.mp4")


class TestGetFilePath:
    def test_returns_local_path(self, tmp_path):
        storage, _ = _make_storage(tmp_path)
        path = storage.get_file_path("video.mp4", "proj")
        assert isinstance(path, Path)
        assert "proj" in str(path)
        assert str(path).endswith("video.mp4")

    def test_no_directory(self, tmp_path):
        storage, _ = _make_storage(tmp_path)
        path = storage.get_file_path("video.mp4")
        assert isinstance(path, Path)
        assert str(path).endswith("video.mp4")


class TestSaveFile:
    @pytest.mark.asyncio
    async def test_uploads_bytes(self, tmp_path):
        storage, bucket = _make_storage(tmp_path)
        blob = MagicMock()
        bucket.blob.return_value = blob

        result = await storage.save_file(b"content", "video.mp4", "proj")

        assert result == "gs://test-bucket/uploads/proj/video.mp4"
        blob.upload_from_string.assert_called_once_with(b"content")


class TestListFiles:
    def test_lists_objects(self, tmp_path):
        storage, _ = _make_storage(tmp_path)
        mock_blob1 = MagicMock()
        mock_blob1.name = "uploads/a.mp4"
        mock_blob2 = MagicMock()
        mock_blob2.name = "uploads/b.mp4"
        storage._client.list_blobs.return_value = [mock_blob1, mock_blob2]

        result = storage.list_files()

        assert result == ["uploads/a.mp4", "uploads/b.mp4"]
