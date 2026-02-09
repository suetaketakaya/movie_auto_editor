"""
Clip scoring and engagement prediction - pure domain logic.
Extracted from legacy engagement_predictor.py.
"""
from __future__ import annotations

import statistics
from typing import Optional

from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.value_objects.quality_score import QualityScore


class ClipScorer:
    """Scores clips based on analysis results for engagement prediction."""

    def score_clip(self, clip: Clip, analyses: list[FrameAnalysis]) -> QualityScore:
        """Calculate quality score for a single clip based on surrounding frame analyses."""
        clip_analyses = [
            a for a in analyses
            if clip.time_range.contains(a.timestamp)
        ]

        if not clip_analyses:
            return QualityScore.zero()

        score = 0.0

        # Average excitement contribution (up to 50 points)
        avg_excitement = statistics.mean([a.excitement_score for a in clip_analyses])
        score += min(50.0, avg_excitement * 2)

        # Duration bonus (5-10s ideal = 20pts, 3-15s acceptable = 10pts)
        duration = clip.duration
        if 5 <= duration <= 10:
            score += 20.0
        elif 3 <= duration <= 15:
            score += 10.0

        # Action density (kills per second, up to 30 points)
        kill_count = sum(1 for a in clip_analyses if a.kill_log)
        action_density = kill_count / duration if duration > 0 else 0
        score += min(30.0, action_density * 100)

        return QualityScore(
            value=min(100.0, score),
            breakdown={
                "excitement": min(50.0, avg_excitement * 2),
                "duration": 20.0 if 5 <= duration <= 10 else (10.0 if 3 <= duration <= 15 else 0.0),
                "action_density": min(30.0, action_density * 100),
            },
        )

    def predict_engagement(self, clips: list[Clip], analyses: list[FrameAnalysis]) -> dict:
        """Predict overall video engagement metrics."""
        if not clips:
            return {
                "overall_score": 0,
                "retention_prediction": 0,
                "click_through_rate": 0,
                "watch_time_minutes": 0.0,
            }

        excitement_scores = [a.excitement_score for a in analyses if a.excitement_score > 0]
        avg_excitement = statistics.mean(excitement_scores) if excitement_scores else 0.0

        clip_lengths = [c.duration for c in clips]
        variety_score = statistics.stdev(clip_lengths) if len(clip_lengths) > 1 else 0.0

        total_duration = sum(clip_lengths)

        return {
            "overall_score": min(100, int(avg_excitement * 2 + variety_score * 5)),
            "retention_prediction": min(100, int((avg_excitement / 30) * 100)) if avg_excitement > 0 else 0,
            "click_through_rate": min(15, int(avg_excitement / 5)),
            "watch_time_minutes": total_duration / 60,
        }

    def detect_drop_off_points(self, clips: list[Clip]) -> list[float]:
        """Detect potential viewer drop-off points."""
        return [c.start for c in clips if c.duration > 15]

    def suggest_improvements(self, clips: list[Clip], analyses: list[FrameAnalysis]) -> list[str]:
        """Suggest improvements for better engagement."""
        suggestions: list[str] = []
        total_duration = sum(c.duration for c in clips)

        if total_duration > 300:
            suggestions.append("Video is too long. Consider trimming to 3-5 minutes.")
        if len(clips) > 15:
            suggestions.append("Too many clips. Focus on the best highlights only.")
        if total_duration < 30:
            suggestions.append("Video is very short. Consider including more clips.")

        return suggestions
