"""Google Cloud Storage implementation of FileStoragePort."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class GCSFileStorage:
    """FileStoragePort backed by Google Cloud Storage.

    Also exposes GCS-specific helpers for resumable upload sessions
    that are not part of the FileStoragePort protocol.
    """

    def __init__(
        self,
        bucket_name: str,
        credentials_path: str = "",
        upload_prefix: str = "uploads/",
        signed_url_expiration_seconds: int = 3600,
        local_cache_dir: str = "./media",
    ) -> None:
        from google.cloud import storage as gcs_storage
        from google.oauth2 import service_account

        self._bucket_name = bucket_name
        self._upload_prefix = upload_prefix
        self._expiration = signed_url_expiration_seconds
        self._local_cache = Path(local_cache_dir)
        self._local_cache.mkdir(parents=True, exist_ok=True)

        if credentials_path:
            creds = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
            )
            self._client = gcs_storage.Client(credentials=creds)
        else:
            self._client = gcs_storage.Client()

        self._bucket = self._client.bucket(bucket_name)
        logger.info("GCSFileStorage initialised (bucket=%s)", bucket_name)

    # ── GCS-specific methods ──────────────────────────────────────

    def create_resumable_upload_session(
        self, gcs_object_name: str, content_type: str = "video/mp4"
    ) -> str:
        """Create a GCS resumable upload session and return the session URI.

        The frontend PUTs chunks directly to this URI with Content-Range headers.
        """
        blob = self._bucket.blob(gcs_object_name)
        upload_url = blob.create_resumable_upload_session(
            content_type=content_type,
            size=None,
        )
        logger.info(
            "Created resumable upload session for gs://%s/%s",
            self._bucket_name,
            gcs_object_name,
        )
        return upload_url

    async def download_to_local(self, gcs_object_name: str, local_path: str) -> str:
        """Download a GCS object to a local path for FFmpeg processing."""
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        blob = self._bucket.blob(gcs_object_name)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, blob.download_to_filename, str(target))
        logger.info(
            "Downloaded gs://%s/%s -> %s",
            self._bucket_name,
            gcs_object_name,
            target,
        )
        return str(target)

    def gcs_object_exists(self, gcs_object_name: str) -> bool:
        """Return True if the GCS object exists."""
        blob = self._bucket.blob(gcs_object_name)
        return blob.exists()

    async def delete_gcs_object(self, gcs_object_name: str) -> None:
        """Delete an object from GCS."""
        blob = self._bucket.blob(gcs_object_name)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, blob.delete)
        logger.info("Deleted gs://%s/%s", self._bucket_name, gcs_object_name)

    # ── FileStoragePort implementation ────────────────────────────

    async def save_file(self, content: bytes, filename: str, directory: str = "") -> str:
        """Upload bytes to GCS. Returns gs://bucket/object path."""
        object_name = f"{self._upload_prefix}{directory}/{filename}".lstrip("/")
        blob = self._bucket.blob(object_name)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, blob.upload_from_string, content)
        return f"gs://{self._bucket_name}/{object_name}"

    def get_file_path(self, filename: str, directory: str = "") -> Path:
        """Return a local cache path placeholder.

        Callers that need the actual file must call download_to_local() first.
        """
        if directory:
            return self._local_cache / directory / filename
        return self._local_cache / filename

    async def delete_file(self, filepath: str) -> None:
        """Delete a file given a gs:// URI or local path."""
        if filepath.startswith("gs://"):
            object_name = filepath[len(f"gs://{self._bucket_name}/"):]
            await self.delete_gcs_object(object_name)
        else:
            local = Path(filepath)
            if local.exists():
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, local.unlink)

    def list_files(self, directory: str = "") -> list[str]:
        """List GCS objects under the upload prefix + directory."""
        prefix = f"{self._upload_prefix}{directory}" if directory else self._upload_prefix
        blobs = self._client.list_blobs(self._bucket_name, prefix=prefix)
        return [b.name for b in blobs]
