"""Local filesystem implementation of FileStoragePort."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LocalFileStorage:
    """Implements :class:`FileStoragePort` using the local filesystem.

    All paths are resolved relative to a configurable *base_dir*.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)
        logger.info("LocalFileStorage initialised at %s", self._base)

    # -- helpers ---------------------------------------------------------------

    def _resolve(self, filename: str, directory: str = "") -> Path:
        """Return an absolute path under the base directory."""
        if directory:
            return self._base / directory / filename
        return self._base / filename

    # -- FileStoragePort implementation ----------------------------------------

    async def save_file(
        self, content: bytes, filename: str, directory: str = ""
    ) -> str:
        """Write *content* to disk and return the absolute path as a string."""
        target = self._resolve(filename, directory)
        target.parent.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, target.write_bytes, content)
        logger.debug("Saved file %s (%d bytes)", target, len(content))
        return str(target)

    def get_file_path(self, filename: str, directory: str = "") -> Path:
        """Return the :class:`Path` object for a given filename."""
        return self._resolve(filename, directory)

    async def delete_file(self, filepath: str) -> None:
        """Delete a file by its absolute or relative path."""
        target = Path(filepath)
        if not target.is_absolute():
            target = self._base / target

        if not target.exists():
            logger.warning("File to delete does not exist: %s", target)
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, target.unlink)
        logger.debug("Deleted file %s", target)

    def list_files(self, directory: str = "") -> list[str]:
        """Return a list of filenames in *directory* (non-recursive)."""
        search_dir = self._base / directory if directory else self._base
        if not search_dir.exists():
            logger.debug("Directory does not exist: %s", search_dir)
            return []
        return [p.name for p in search_dir.iterdir() if p.is_file()]
