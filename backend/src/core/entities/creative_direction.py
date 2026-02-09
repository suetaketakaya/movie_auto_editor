"""CreativeDirection entity for video editing parameters."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CreativeDirection:
    """Parameters controlling the creative direction of the video output."""

    pacing_strategy: str = "dynamic"
    color_palette: str = "cinematic"
    transition_style: str = "fade"
    audio_style: str = "enhanced"
    text_style: str = "bold"
    hook_strategy: str = "best_moment"
    target_audience: str = "general"
    mood: str = "exciting"
    parameters: dict = field(default_factory=dict)
