"""Clip entity representing a detected highlight clip within a video."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from backend.src.core.value_objects.quality_score import QualityScore
from backend.src.core.value_objects.time_range import TimeRange


@dataclass
class Clip:
    """A highlight clip extracted from a source video."""

    time_range: TimeRange
    reason: str = ""
    score: QualityScore = field(default_factory=QualityScore.zero)
    clip_type: str = ""
    label: str = ""
    priority: int = 0
    action_intensity: str = "low"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.time_range.duration

    @property
    def start(self) -> float:
        return self.time_range.start_seconds

    @property
    def end(self) -> float:
        return self.time_range.end_seconds

    def with_adjusted_range(self, new_range: TimeRange) -> Clip:
        return Clip(
            time_range=new_range,
            reason=self.reason,
            score=self.score,
            clip_type=self.clip_type,
            label=self.label,
            priority=self.priority,
            action_intensity=self.action_intensity,
            id=self.id,
            metadata=self.metadata,
        )

    def with_score(self, new_score: QualityScore) -> Clip:
        return Clip(
            time_range=self.time_range,
            reason=self.reason,
            score=new_score,
            clip_type=self.clip_type,
            label=self.label,
            priority=self.priority,
            action_intensity=self.action_intensity,
            id=self.id,
            metadata=self.metadata,
        )

    def to_legacy_dict(self) -> dict:
        """Convert to legacy dict format."""
        return {
            "start": self.start,
            "end": self.end,
            "reason": self.reason,
            "score": self.score.value,
            "type": self.clip_type,
            "label": self.label,
            "priority": self.priority,
            "action_intensity": self.action_intensity,
        }

    @classmethod
    def from_legacy_dict(cls, data: dict) -> Clip:
        """Create from legacy dict format."""
        return cls(
            time_range=TimeRange(
                start_seconds=data.get("start", 0.0),
                end_seconds=data.get("end", 1.0),
            ),
            reason=data.get("reason", ""),
            score=QualityScore(value=data.get("score", 0.0)),
            clip_type=data.get("type", ""),
            label=data.get("label", ""),
            priority=data.get("priority", 0),
            action_intensity=data.get("action_intensity", "low"),
        )
