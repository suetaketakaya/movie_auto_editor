"""Port for video editing operations."""
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol, runtime_checkable
if TYPE_CHECKING:
    from backend.src.core.entities.clip import Clip


@runtime_checkable
class VideoEditingPort(Protocol):
    async def create_highlight(self, input_video: str, clips: list[Clip], output_path: str) -> str: ...
    def get_video_metadata(self, video_path: str) -> dict: ...
    def create_vertical_crop(self, input_video: str, output_path: str, position: str = "center") -> str: ...
