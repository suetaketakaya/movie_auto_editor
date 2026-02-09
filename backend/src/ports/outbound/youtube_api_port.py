"""Port for YouTube Data API operations."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class YouTubeAPIPort(Protocol):
    async def get_video_stats(self, video_id: str) -> dict: ...
    async def get_channel_stats(self, channel_id: str) -> dict: ...
