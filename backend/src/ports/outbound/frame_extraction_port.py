"""Port for frame extraction from video files."""
from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class FrameExtractionPort(Protocol):
    async def extract_frames(self, video_path: str, output_dir: Path, interval_seconds: float = 2.0, max_frames: int = 2000) -> list[str]: ...
    def get_video_info(self, video_path: str) -> dict: ...
