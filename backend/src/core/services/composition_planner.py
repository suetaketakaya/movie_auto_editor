"""
Video composition planning and optimization - pure domain logic.
Extracted from legacy composition_optimizer.py.
"""
from __future__ import annotations

import statistics
from typing import Optional

from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.value_objects.quality_score import QualityScore
from backend.src.core.value_objects.time_range import TimeRange


class CompositionPlanner:
    """Plans and optimizes video clip composition for maximum engagement."""

    def __init__(
        self,
        target_duration: float = 180.0,
        min_clip_length: float = 3.0,
        max_clip_length: float = 15.0,
        optimal_pace: float = 5.0,
    ):
        self.target_duration = target_duration
        self.min_clip_length = min_clip_length
        self.max_clip_length = max_clip_length
        self.optimal_pace = optimal_pace

    def optimize_clips(self, clips: list[Clip], analyses: list[FrameAnalysis]) -> list[Clip]:
        """Full optimization pipeline."""
        scored = self.score_clips(clips, analyses)
        adjusted = self.adjust_clip_lengths(scored)
        sorted_clips = sorted(adjusted, key=lambda c: c.score.value, reverse=True)
        trimmed = self.trim_to_target_duration(sorted_clips)
        return self.optimize_pacing(trimmed)

    def score_clips(self, clips: list[Clip], analyses: list[FrameAnalysis]) -> list[Clip]:
        """Assign scores to clips based on analysis results."""
        scored: list[Clip] = []
        for clip in clips:
            mid_time = clip.time_range.midpoint
            closest = min(analyses, key=lambda a: abs(a.timestamp - mid_time), default=None)

            score = 0.0
            action_intensity = clip.action_intensity

            if closest:
                if closest.kill_log:
                    score += 10
                intensity_scores = {"very_high": 8, "high": 6, "medium": 4, "low": 2}
                score += intensity_scores.get(closest.action_intensity, 0)
                action_intensity = closest.action_intensity

                if closest.match_status == "victory":
                    score += 5
                elif closest.match_status == "clutch":
                    score += 7

            duration = clip.duration
            if duration > self.max_clip_length:
                score -= 2
            elif duration < self.min_clip_length:
                score -= 1

            new_clip = Clip(
                time_range=clip.time_range,
                reason=clip.reason,
                score=QualityScore(value=max(0, score)),
                clip_type=clip.clip_type,
                label=clip.label,
                priority=clip.priority,
                action_intensity=action_intensity,
                id=clip.id,
                metadata=clip.metadata,
            )
            scored.append(new_clip)
        return scored

    def adjust_clip_lengths(self, clips: list[Clip]) -> list[Clip]:
        """Adjust clip durations to fit within min/max bounds."""
        adjusted: list[Clip] = []
        for clip in clips:
            duration = clip.duration
            if duration > self.max_clip_length:
                center = clip.time_range.midpoint
                half = self.max_clip_length / 2
                new_range = TimeRange(
                    start_seconds=max(clip.start, center - half),
                    end_seconds=min(clip.end, center + half),
                )
                adjusted.append(clip.with_adjusted_range(new_range))
            elif duration < self.min_clip_length:
                extension = (self.min_clip_length - duration) / 2
                new_range = TimeRange(
                    start_seconds=max(0, clip.start - extension),
                    end_seconds=clip.end + extension,
                )
                adjusted.append(clip.with_adjusted_range(new_range))
            else:
                adjusted.append(clip)
        return adjusted

    def trim_to_target_duration(self, clips: list[Clip]) -> list[Clip]:
        """Trim clip list to fit target duration."""
        if not clips:
            return clips

        current_duration = self._total_duration(clips)
        if current_duration <= self.target_duration:
            return clips

        trimmed: list[Clip] = []
        accumulated = 0.0
        for clip in clips:
            if accumulated + clip.duration <= self.target_duration:
                trimmed.append(clip)
                accumulated += clip.duration
            else:
                remaining = self.target_duration - accumulated
                if remaining >= self.min_clip_length:
                    new_range = TimeRange(clip.start, clip.start + remaining)
                    trimmed.append(clip.with_adjusted_range(new_range))
                break
        return trimmed

    def optimize_pacing(self, clips: list[Clip]) -> list[Clip]:
        """Interleave high and medium intensity clips for engaging rhythm."""
        if len(clips) <= 2:
            return clips

        high = [c for c in clips if c.action_intensity in ("very_high", "high")]
        medium = [c for c in clips if c.action_intensity == "medium"]
        low = [c for c in clips if c.action_intensity == "low"]

        optimized: list[Clip] = []
        hi_idx, mi_idx = 0, 0

        if high:
            optimized.append(high[hi_idx])
            hi_idx += 1

        while hi_idx < len(high) or mi_idx < len(medium):
            if mi_idx < len(medium):
                optimized.append(medium[mi_idx])
                mi_idx += 1
            if hi_idx < len(high):
                optimized.append(high[hi_idx])
                hi_idx += 1

        optimized.extend(low[:2])
        return optimized

    def create_hook_intro(self, clips: list[Clip]) -> Optional[Clip]:
        """Create a 3-second hook from the best clip."""
        if not clips:
            return None
        best = max(clips, key=lambda c: c.score.value)
        mid = best.time_range.midpoint
        hook_range = TimeRange(start_seconds=max(0, mid - 1.5), end_seconds=mid + 1.5)
        return Clip(
            time_range=hook_range,
            reason="hook",
            score=best.score,
            clip_type="hook",
            label="HOOK",
            metadata={"is_hook": True},
        )

    def analyze_engagement_curve(self, clips: list[Clip]) -> dict:
        """Analyze the engagement curve of the clip sequence."""
        if not clips:
            return {"status": "no_clips"}
        scores = [c.score.value for c in clips]
        return {
            "avg_score": statistics.mean(scores) if scores else 0,
            "score_variance": statistics.variance(scores) if len(scores) > 1 else 0,
            "peak_moment": max(range(len(scores)), key=lambda i: scores[i]) if scores else 0,
            "total_duration": self._total_duration(clips),
            "clip_count": len(clips),
            "pacing_score": self._calculate_pacing_score(clips),
        }

    def _calculate_pacing_score(self, clips: list[Clip]) -> float:
        """Calculate how close the pacing is to optimal."""
        if not clips:
            return 0.0
        durations = [c.duration for c in clips]
        avg_duration = statistics.mean(durations)
        deviation = abs(avg_duration - self.optimal_pace)
        return max(0.0, 100.0 - deviation * 10)

    def _total_duration(self, clips: list[Clip]) -> float:
        return sum(c.duration for c in clips)
