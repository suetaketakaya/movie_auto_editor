"""Timeline entity - ordered collection of clips forming the final composition."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.src.core.entities.clip import Clip
from backend.src.core.entities.content_type import ContentType


@dataclass
class Timeline:
    """Ordered sequence of clips forming the final video composition."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    clips: list[Clip] = field(default_factory=list)
    target_duration: float = 180.0
    content_type: ContentType = ContentType.GENERAL

    @property
    def total_duration(self) -> float:
        return sum(c.duration for c in self.clips)

    @property
    def clip_count(self) -> int:
        return len(self.clips)

    @property
    def average_clip_duration(self) -> float:
        if not self.clips:
            return 0.0
        return self.total_duration / len(self.clips)

    @property
    def has_hook(self) -> bool:
        return len(self.clips) > 0 and self.clips[0].metadata.get("is_hook", False)

    def add_clip(self, clip: Clip) -> None:
        self.clips.append(clip)

    def remove_clip(self, clip_id: str) -> None:
        self.clips = [c for c in self.clips if c.id != clip_id]

    def reorder_by_score(self) -> None:
        self.clips.sort(key=lambda c: c.score.value, reverse=True)

    def get_engagement_curve(self) -> list[float]:
        return [c.score.value for c in self.clips]

    def to_clip_list(self) -> list[dict]:
        """Convert to legacy list of dicts."""
        return [c.to_legacy_dict() for c in self.clips]
