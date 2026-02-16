"""FrameAnalysis entity representing AI analysis of a single video frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FrameAnalysis:
    """Result of AI vision analysis on a single frame.

    Replaces the raw dict structures used in the legacy code.
    """

    frame_path: str = ""
    timestamp: float = 0.0
    kill_log: bool = False
    match_status: str = "unknown"
    action_intensity: str = "low"
    enemy_visible: bool = False
    scene_description: str = ""
    confidence: float = 0.0
    excitement_score: float = 0.0
    model_used: str = ""
    raw_response: Optional[str] = None
    ui_elements: str = ""
    metadata: dict = field(default_factory=dict)
    # Extended fields for improved analysis
    kill_count: int = 0
    enemy_count: int = 0
    visual_quality: str = "normal"  # "low", "normal", "high", "cinematic"

    def to_legacy_dict(self) -> dict:
        """Convert back to the legacy dict format for backward compatibility."""
        return {
            "frame_path": self.frame_path,
            "timestamp": self.timestamp,
            "kill_log": self.kill_log,
            "match_status": self.match_status,
            "action_intensity": self.action_intensity,
            "enemy_visible": self.enemy_visible,
            "scene_description": self.scene_description,
            "confidence": self.confidence,
            "excitement_score": self.excitement_score,
            "kill_count": self.kill_count,
            "enemy_count": self.enemy_count,
            "visual_quality": self.visual_quality,
        }

    @classmethod
    def from_legacy_dict(cls, data: dict) -> FrameAnalysis:
        """Create from the legacy dict format."""
        known_keys = {
            "frame_path", "timestamp", "kill_log", "match_status",
            "action_intensity", "enemy_visible", "scene_description",
            "confidence", "excitement_score", "model_used", "raw_response",
            "ui_elements", "kill_count", "enemy_count", "visual_quality",
        }
        return cls(
            frame_path=data.get("frame_path", ""),
            timestamp=data.get("timestamp", 0.0),
            kill_log=data.get("kill_log", False),
            match_status=data.get("match_status", "unknown"),
            action_intensity=data.get("action_intensity", "low"),
            enemy_visible=data.get("enemy_visible", False),
            scene_description=data.get("scene_description", ""),
            confidence=data.get("confidence", 0.0),
            excitement_score=data.get("excitement_score", 0.0),
            model_used=data.get("model_used", ""),
            raw_response=data.get("raw_response"),
            ui_elements=data.get("ui_elements", ""),
            kill_count=data.get("kill_count", 0),
            enemy_count=data.get("enemy_count", 0),
            visual_quality=data.get("visual_quality", "normal"),
            metadata={k: v for k, v in data.items() if k not in known_keys},
        )
