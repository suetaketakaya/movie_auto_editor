"""
FPS Montage plugin - extracts current FPS-specific logic into a plugin.
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


class FPSMontagePlugin(ContentPlugin):
    """Plugin for FPS game montage/highlight videos."""

    @property
    def name(self) -> str:
        return "fps_montage"

    @property
    def display_name(self) -> str:
        return "FPS Montage"

    def get_director_config(self) -> DirectorConfig:
        return DirectorConfig(
            min_clip_length=3.0,
            max_clip_length=15.0,
            target_duration=180.0,
            hook_duration=3.0,
            pacing_variation=0.6,
            excitement_threshold=20.0,
            transition_style="fade",
            color_preset="cinematic",
            audio_music_ratio=0.3,
            text_overlay_freq=0.7,
            extra={"kill_counter": True, "multi_kill_popup": True},
        )

    def get_quality_metrics(self) -> QualityMetrics:
        return QualityMetrics(
            min_score=70.0,
            required_clip_types=["multi_kill", "high_excitement"],
            max_duration_deviation=30.0,
            min_clips=3,
        )

    def get_vision_prompt_override(self) -> Optional[str]:
        return """Analyze this FPS game screenshot and provide a JSON response with the following fields:

{
    "kill_log": boolean,
    "match_status": string,  // "playing", "victory", "defeat", "clutch", "result_screen", "unknown"
    "action_intensity": string,  // "low", "medium", "high", "very_high"
    "enemy_visible": boolean,
    "ui_elements": string,
    "scene_description": string,
    "confidence": float  // 0.0-1.0
}

Only respond with valid JSON, no additional text."""

    def preprocess(self, analyses: list[FrameAnalysis]) -> list[FrameAnalysis]:
        """Boost excitement for kill-related frames."""
        processed: list[FrameAnalysis] = []
        for a in analyses:
            excitement = a.excitement_score
            # Boost kill events
            if a.kill_log:
                excitement = max(excitement, 20.0)
            # Boost clutch moments
            if a.match_status == "clutch":
                excitement = max(excitement, 25.0)
            # Boost very high action
            if a.action_intensity == "very_high":
                excitement = max(excitement, 15.0)

            if excitement != a.excitement_score:
                processed.append(FrameAnalysis(
                    frame_path=a.frame_path,
                    timestamp=a.timestamp,
                    kill_log=a.kill_log,
                    match_status=a.match_status,
                    action_intensity=a.action_intensity,
                    enemy_visible=a.enemy_visible,
                    scene_description=a.scene_description,
                    confidence=a.confidence,
                    excitement_score=excitement,
                    model_used=a.model_used,
                    raw_response=a.raw_response,
                    ui_elements=a.ui_elements,
                    metadata=a.metadata,
                ))
            else:
                processed.append(a)
        return processed

    def postprocess_clips(self, clips: list[Clip]) -> list[Clip]:
        """Prioritize multi-kill clips in FPS content."""
        for clip in clips:
            if clip.clip_type == "multi_kill":
                clip = clip.with_score(
                    clip.score.with_bonus(10.0, "multi_kill_bonus")
                )
        return sorted(clips, key=lambda c: c.score.value, reverse=True)
