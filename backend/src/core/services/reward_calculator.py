"""
Reward calculation for reinforcement learning experiments.
Combines multiple quality signals into a composite reward.
"""
from __future__ import annotations

import statistics
from typing import Optional

from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.value_objects.quality_score import QualityScore
from backend.src.core.value_objects.reward_signal import DEFAULT_WEIGHTS, RewardSignal


class RewardCalculator:
    """Calculates composite reward signals from multiple quality metrics."""

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def calculate(self, metrics: dict[str, float]) -> RewardSignal:
        """Calculate composite reward from individual 0-1 normalized metrics."""
        return RewardSignal.compute(metrics, self.weights)

    def calculate_from_clips(
        self,
        clips: list[Clip],
        analyses: list[FrameAnalysis],
        quality_score: QualityScore,
        target_duration: float = 180.0,
    ) -> RewardSignal:
        """Calculate reward from actual processing results."""
        if not clips:
            return RewardSignal(total=0.0, components={}, weights=self.weights)

        # Retention: based on pacing (variety of clip lengths)
        durations = [c.duration for c in clips]
        pace_deviation = abs(statistics.mean(durations) - 5.0) if durations else 10.0
        retention = max(0.0, min(1.0, 1.0 - pace_deviation / 10.0))

        # CTR: proxy from best clip score
        best_score = max((c.score.value for c in clips), default=0)
        ctr = min(1.0, best_score / 100.0)

        # Engagement: average excitement
        excitement_scores = [a.excitement_score for a in analyses if a.excitement_score > 0]
        avg_excitement = statistics.mean(excitement_scores) if excitement_scores else 0
        engagement = min(1.0, avg_excitement / 35.0)

        # Watch time: how close to target duration
        total_dur = sum(durations)
        duration_ratio = total_dur / target_duration if target_duration > 0 else 0
        watch_time = max(0.0, 1.0 - abs(1.0 - duration_ratio))

        # LLM quality: from the quality score
        llm_quality = quality_score.value / 100.0

        # Diversity: clip type variety
        types = set(c.clip_type for c in clips if c.clip_type)
        diversity = min(1.0, len(types) / 4.0)

        components = {
            "retention": retention,
            "ctr": ctr,
            "engagement": engagement,
            "watch_time": watch_time,
            "llm_quality": llm_quality,
            "diversity": diversity,
        }
        return RewardSignal.compute(components, self.weights)

    def ablate(self, component_name: str) -> RewardCalculator:
        """Return a new calculator with one component removed and weights renormalized."""
        new_weights = {k: v for k, v in self.weights.items() if k != component_name}
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v / total for k, v in new_weights.items()}
        return RewardCalculator(weights=new_weights)
