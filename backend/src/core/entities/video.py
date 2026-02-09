"""Video entity representing a source video file."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Video:
    """Represents a source video file and its metadata."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    file_path: str = ""
    duration_seconds: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""
    file_size_bytes: int = 0
    uploaded_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def resolution_str(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def aspect_ratio(self) -> float:
        if self.height == 0:
            return 0.0
        return self.width / self.height

    @property
    def is_vertical(self) -> bool:
        return self.height > self.width

    @property
    def duration_formatted(self) -> str:
        minutes = int(self.duration_seconds // 60)
        seconds = int(self.duration_seconds % 60)
        return f"{minutes}:{seconds:02d}"
