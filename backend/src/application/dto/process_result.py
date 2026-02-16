"""DTO for video processing results."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProcessResult:
    project_id: str
    success: bool = True
    output_video_path: str = ""
    clips: list = field(default_factory=list)
    quality_score: float = 0.0
    reward_signal: float = 0.0
    reward_components: dict = field(default_factory=dict)
    engagement_curve: dict = field(default_factory=dict)
    multi_events: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    clip_count: int = 0
    total_duration: float = 0.0
    error: Optional[str] = None
    warnings: list = field(default_factory=list)
    thumbnail_path: str = ""

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "success": self.success,
            "output_video_path": self.output_video_path,
            "clips": self.clips,
            "quality_score": self.quality_score,
            "reward_signal": self.reward_signal,
            "reward_components": self.reward_components,
            "engagement_curve": self.engagement_curve,
            "multi_events": self.multi_events,
            "suggestions": self.suggestions,
            "clip_count": self.clip_count,
            "total_duration": self.total_duration,
            "error": self.error,
            "warnings": self.warnings,
            "thumbnail_path": self.thumbnail_path,
        }
