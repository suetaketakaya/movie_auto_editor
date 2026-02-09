"""
General plugin - fallback for content types without a dedicated plugin.
"""
from __future__ import annotations

from typing import Optional

from backend.src.application.plugins.base_content_plugin import (
    ContentPlugin,
    DirectorConfig,
    QualityMetrics,
)
from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip


class GeneralPlugin(ContentPlugin):
    """Generic fallback plugin with relaxed defaults."""

    @property
    def name(self) -> str:
        return "general"

    @property
    def display_name(self) -> str:
        return "General"

    def get_director_config(self) -> DirectorConfig:
        return DirectorConfig(
            min_clip_length=3.0,
            max_clip_length=15.0,
            target_duration=180.0,
            hook_duration=3.0,
            pacing_variation=0.5,
            excitement_threshold=10.0,
            transition_style="fade",
            color_preset="cinematic",
            audio_music_ratio=0.3,
            text_overlay_freq=0.5,
        )

    def get_quality_metrics(self) -> QualityMetrics:
        return QualityMetrics(
            min_score=50.0,
            required_clip_types=[],
            max_duration_deviation=60.0,
            min_clips=1,
        )

    def get_vision_prompt_override(self) -> Optional[str]:
        return None

    def preprocess(self, analyses: list[FrameAnalysis]) -> list[FrameAnalysis]:
        """Pass through analyses unchanged."""
        return analyses

    def postprocess_clips(self, clips: list[Clip]) -> list[Clip]:
        """Sort by score descending, no content-specific boosting."""
        return sorted(clips, key=lambda c: c.score.value, reverse=True)
