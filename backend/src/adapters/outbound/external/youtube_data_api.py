"""YouTube Data API adapter implementing YouTubeAPIPort.

Uses the ``google-api-python-client`` library.  All methods are async-friendly
by delegating blocking HTTP calls to a thread-pool executor.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class YouTubeDataAPIAdapter:
    """Implements :class:`YouTubeAPIPort` using the YouTube Data API v3.

    Requires a valid API key or OAuth2 credentials.  When *credentials* is
    ``None`` the adapter works in "dry-run" mode and returns placeholder data.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        credentials: Optional[Any] = None,
    ) -> None:
        self._api_key = api_key
        self._credentials = credentials
        self._service: Optional[Any] = None
        self._initialised = False

    # -- lazy initialisation ---------------------------------------------------

    def _ensure_service(self) -> Any:
        """Build the ``youtube`` service object on first use."""
        if self._service is not None:
            return self._service

        try:
            from googleapiclient.discovery import build  # type: ignore[import-untyped]

            if self._credentials is not None:
                self._service = build(
                    "youtube", "v3", credentials=self._credentials
                )
            elif self._api_key is not None:
                self._service = build(
                    "youtube", "v3", developerKey=self._api_key
                )
            else:
                logger.warning(
                    "No API key or credentials supplied; "
                    "YouTubeDataAPIAdapter running in dry-run mode"
                )
                return None
        except ImportError:
            logger.error(
                "google-api-python-client is not installed. "
                "Install it with: pip install google-api-python-client"
            )
            return None

        self._initialised = True
        return self._service

    # -- YouTubeAPIPort implementation -----------------------------------------

    async def get_video_stats(self, video_id: str) -> dict:
        """Fetch statistics for a single YouTube video."""
        service = self._ensure_service()
        if service is None:
            logger.warning("Dry-run: returning placeholder stats for %s", video_id)
            return {
                "video_id": video_id,
                "view_count": 0,
                "like_count": 0,
                "comment_count": 0,
            }

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: service.videos()
            .list(part="statistics", id=video_id)
            .execute(),
        )

        items = response.get("items", [])
        if not items:
            logger.warning("No video found for id %s", video_id)
            return {"video_id": video_id}

        stats = items[0].get("statistics", {})
        return {
            "video_id": video_id,
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
        }

    async def get_channel_stats(self, channel_id: str) -> dict:
        """Fetch statistics for a YouTube channel."""
        service = self._ensure_service()
        if service is None:
            logger.warning(
                "Dry-run: returning placeholder channel stats for %s", channel_id
            )
            return {
                "channel_id": channel_id,
                "subscriber_count": 0,
                "video_count": 0,
                "view_count": 0,
            }

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: service.channels()
            .list(part="statistics", id=channel_id)
            .execute(),
        )

        items = response.get("items", [])
        if not items:
            logger.warning("No channel found for id %s", channel_id)
            return {"channel_id": channel_id}

        stats = items[0].get("statistics", {})
        return {
            "channel_id": channel_id,
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
        }
