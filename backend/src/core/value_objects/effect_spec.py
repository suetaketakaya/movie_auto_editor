"""EffectSpec value object - specification for a visual/audio effect."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.src.core.value_objects.time_range import TimeRange


class EffectType(str, Enum):
    COLOR_GRADING = "color_grading"
    VIGNETTE = "vignette"
    SLOW_MOTION = "slow_motion"
    ZOOM = "zoom"
    SHAKE = "shake"
    CHROMATIC_ABERRATION = "chromatic_aberration"
    TRANSITION = "transition"
    TEXT_OVERLAY = "text_overlay"
    AUDIO_FADE = "audio_fade"
    AUDIO_NORMALIZE = "audio_normalize"
    BASS_BOOST = "bass_boost"
    BACKGROUND_MUSIC = "background_music"
    DENOISE = "denoise"
    SHARPEN = "sharpen"
    FILM_GRAIN = "film_grain"
    STABILIZE = "stabilize"


@dataclass(frozen=True)
class EffectSpec:
    """Immutable specification for an effect to be applied to video/audio."""

    effect_type: EffectType
    parameters: dict = field(default_factory=dict)
    time_range: Optional[TimeRange] = None
    priority: int = 0
