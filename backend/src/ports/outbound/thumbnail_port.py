"""Port for thumbnail generation."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class ThumbnailPort(Protocol):
    def extract_best_frame(self, video_path: str, timestamp: float, output_path: str) -> str: ...
    def create_youtube_thumbnail(self, frame_path: str, output_path: str, title_text: str = "", kill_count: int = 0) -> str: ...
    def generate_ab_variants(self, video_path: str, output_dir: str, title: str = "", kill_count: int = 0) -> list[str]: ...
