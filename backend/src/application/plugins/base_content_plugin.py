"""
Base content plugin defining the interface for content-type-specific processing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.entities.creative_direction import CreativeDirection


@dataclass
class DirectorConfig:
    """Configuration passed to the 3-director system."""
    min_clip_length: float = 3.0
    max_clip_length: float = 15.0
    target_duration: float = 180.0
    hook_duration: float = 3.0
    pacing_variation: float = 0.5
    excitement_threshold: float = 20.0
    transition_style: str = "fade"
    color_preset: str = "cinematic"
    audio_music_ratio: float = 0.3
    text_overlay_freq: float = 0.5
    extra: dict = field(default_factory=dict)


@dataclass
class QualityMetrics:
    """Content-type-specific quality criteria."""
    min_score: float = 70.0
    required_clip_types: list[str] = field(default_factory=list)
    max_duration_deviation: float = 30.0
    min_clips: int = 3
    extra: dict = field(default_factory=dict)


class ContentPlugin(ABC):
    """Base class for content-type plugins.

    Each plugin customizes the processing pipeline for a specific
    content type (FPS montage, sports highlight, MAD/AMV, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        ...

    @abstractmethod
    def get_director_config(self) -> DirectorConfig:
        """Return default director configuration for this content type."""
        ...

    @abstractmethod
    def get_quality_metrics(self) -> QualityMetrics:
        """Return quality criteria for this content type."""
        ...

    @abstractmethod
    def preprocess(self, analyses: list[FrameAnalysis]) -> list[FrameAnalysis]:
        """Content-specific preprocessing of frame analyses.

        Can filter, re-score, or annotate analyses before clip selection.
        """
        ...

    @abstractmethod
    def postprocess_clips(self, clips: list[Clip]) -> list[Clip]:
        """Content-specific post-processing of selected clips."""
        ...

    def get_vision_prompt_override(self) -> Optional[str]:
        """Override the default vision analysis prompt for this content type."""
        return None

    def get_creative_direction(self) -> Optional[CreativeDirection]:
        """Return a default creative direction for this content type."""
        return None

    def validate_output(self, clips: list[Clip], total_duration: float) -> list[str]:
        """Validate output against content-type quality metrics.

        Returns list of issues (empty if valid).
        """
        metrics = self.get_quality_metrics()
        issues: list[str] = []

        if len(clips) < metrics.min_clips:
            issues.append(f"Too few clips: {len(clips)} < {metrics.min_clips}")

        target = self.get_director_config().target_duration
        if abs(total_duration - target) > metrics.max_duration_deviation:
            issues.append(
                f"Duration deviation too large: {total_duration:.1f}s vs target {target:.1f}s"
            )

        return issues
