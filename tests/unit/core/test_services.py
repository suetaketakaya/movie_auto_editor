"""Unit tests for core domain services."""
from __future__ import annotations

import pytest

from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.services.clip_scorer import ClipScorer
from backend.src.core.services.composition_planner import CompositionPlanner
from backend.src.core.services.highlight_detector import HighlightDetector
from backend.src.core.services.reward_calculator import RewardCalculator
from backend.src.core.value_objects.quality_score import QualityScore
from backend.src.core.value_objects.time_range import TimeRange


class TestClipScorer:
    """Tests for ClipScorer service."""

    def test_score_clip_basic(self):
        scorer = ClipScorer()
        clip = Clip(time_range=TimeRange(start_seconds=10.0, end_seconds=18.0))
        analyses = [
            FrameAnalysis(timestamp=12.0, kill_log=True, excitement_score=25.0),
            FrameAnalysis(timestamp=15.0, kill_log=False, excitement_score=20.0),
        ]
        score = scorer.score_clip(clip, analyses)
        assert score.value > 0

    def test_score_clip_no_analyses(self):
        scorer = ClipScorer()
        clip = Clip(time_range=TimeRange(start_seconds=100.0, end_seconds=110.0))
        analyses = [
            FrameAnalysis(timestamp=5.0, excitement_score=10.0),
        ]
        score = scorer.score_clip(clip, analyses)
        assert score.value == 0.0

    def test_predict_engagement(self, sample_clips, sample_analyses):
        scorer = ClipScorer()
        result = scorer.predict_engagement(sample_clips, sample_analyses)
        assert "overall_score" in result
        assert "retention_prediction" in result
        assert "watch_time_minutes" in result

    def test_predict_engagement_empty(self):
        scorer = ClipScorer()
        result = scorer.predict_engagement([], [])
        assert result["overall_score"] == 0
        assert result["watch_time_minutes"] == 0.0

    def test_detect_drop_off_points(self):
        scorer = ClipScorer()
        clips = [
            Clip(time_range=TimeRange(0.0, 5.0)),
            Clip(time_range=TimeRange(5.0, 25.0)),  # > 15s
            Clip(time_range=TimeRange(25.0, 35.0)),
        ]
        drop_offs = scorer.detect_drop_off_points(clips)
        assert len(drop_offs) == 1
        assert drop_offs[0] == 5.0

    def test_suggest_improvements(self, sample_clips, sample_analyses):
        scorer = ClipScorer()
        suggestions = scorer.suggest_improvements(sample_clips, sample_analyses)
        assert isinstance(suggestions, list)


class TestCompositionPlanner:
    """Tests for CompositionPlanner service."""

    def test_optimize_clips(self, sample_clips, sample_analyses):
        planner = CompositionPlanner(target_duration=180.0)
        optimized = planner.optimize_clips(sample_clips, sample_analyses)
        assert isinstance(optimized, list)

    def test_score_clips(self, sample_clips, sample_analyses):
        planner = CompositionPlanner()
        scored = planner.score_clips(sample_clips, sample_analyses)
        assert len(scored) == len(sample_clips)
        for clip in scored:
            assert clip.score.value >= 0

    def test_adjust_clip_lengths_too_long(self):
        planner = CompositionPlanner(max_clip_length=10.0)
        clips = [Clip(time_range=TimeRange(0.0, 20.0))]
        adjusted = planner.adjust_clip_lengths(clips)
        assert adjusted[0].duration <= 10.0

    def test_adjust_clip_lengths_too_short(self):
        planner = CompositionPlanner(min_clip_length=5.0)
        clips = [Clip(time_range=TimeRange(10.0, 12.0))]  # 2s duration
        adjusted = planner.adjust_clip_lengths(clips)
        assert adjusted[0].duration >= 5.0

    def test_trim_to_target_duration(self):
        planner = CompositionPlanner(target_duration=20.0)
        clips = [
            Clip(time_range=TimeRange(0.0, 10.0), score=QualityScore(value=90.0)),
            Clip(time_range=TimeRange(10.0, 20.0), score=QualityScore(value=80.0)),
            Clip(time_range=TimeRange(20.0, 30.0), score=QualityScore(value=70.0)),
        ]
        trimmed = planner.trim_to_target_duration(clips)
        total = sum(c.duration for c in trimmed)
        assert total <= 20.0

    def test_create_hook_intro(self, sample_clips):
        planner = CompositionPlanner()
        hook = planner.create_hook_intro(sample_clips)
        assert hook is not None
        assert hook.clip_type == "hook"
        assert hook.metadata.get("is_hook") is True

    def test_analyze_engagement_curve(self, sample_clips):
        planner = CompositionPlanner()
        curve = planner.analyze_engagement_curve(sample_clips)
        assert "avg_score" in curve
        assert "clip_count" in curve
        assert "pacing_score" in curve


class TestHighlightDetector:
    """Tests for HighlightDetector service."""

    def test_analyze_excitement_levels(self, sample_analyses):
        detector = HighlightDetector()
        enhanced = detector.analyze_excitement_levels(sample_analyses)
        assert len(enhanced) == len(sample_analyses)
        for analysis in enhanced:
            assert analysis.excitement_score >= 0

    def test_detect_multi_events(self):
        detector = HighlightDetector()
        analyses = [
            FrameAnalysis(timestamp=10.0, kill_log=True),
            FrameAnalysis(timestamp=12.0, kill_log=True),
            FrameAnalysis(timestamp=14.0, kill_log=True),
            FrameAnalysis(timestamp=50.0, kill_log=True),
        ]
        events = detector.detect_multi_events(analyses, time_window=10.0)
        assert len(events) >= 1
        assert events[0]["type"] == "TRIPLE KILL"

    def test_detect_multi_events_no_kills(self):
        detector = HighlightDetector()
        analyses = [
            FrameAnalysis(timestamp=10.0, kill_log=False),
            FrameAnalysis(timestamp=20.0, kill_log=False),
        ]
        events = detector.detect_multi_events(analyses)
        assert len(events) == 0

    def test_detect_clutch_moments(self):
        detector = HighlightDetector()
        analyses = [
            FrameAnalysis(timestamp=10.0, match_status="normal"),
            FrameAnalysis(timestamp=20.0, match_status="clutch"),
            FrameAnalysis(timestamp=30.0, match_status="normal"),
        ]
        clutches = detector.detect_clutch_moments(analyses)
        assert len(clutches) == 1
        assert clutches[0]["timestamp"] == 20.0

    def test_suggest_highlights(self):
        detector = HighlightDetector()
        analyses = [
            FrameAnalysis(timestamp=10.0, excitement_score=30.0),
            FrameAnalysis(timestamp=20.0, excitement_score=15.0),
        ]
        multi_events = [{"type": "DOUBLE KILL", "timestamp": 10.0, "end_timestamp": 12.0, "kill_count": 2}]
        clutches = []
        highlights = detector.suggest_highlights(analyses, multi_events, clutches)
        assert len(highlights) > 0

    def test_merge_overlapping_clips(self):
        detector = HighlightDetector()
        clips = [
            Clip(time_range=TimeRange(10.0, 20.0), priority=5),
            Clip(time_range=TimeRange(15.0, 25.0), priority=3),
            Clip(time_range=TimeRange(30.0, 40.0), priority=7),
        ]
        merged = detector.merge_overlapping_clips(clips)
        assert len(merged) == 2

    def test_analyze_variety(self, sample_clips):
        detector = HighlightDetector()
        variety = detector.analyze_variety(sample_clips)
        assert "variety_score" in variety
        assert "unique_types" in variety


class TestRewardCalculator:
    """Tests for RewardCalculator service."""

    def test_calculate(self):
        calc = RewardCalculator()
        metrics = {
            "retention": 0.8,
            "ctr": 0.6,
            "engagement": 0.7,
            "watch_time": 0.5,
            "llm_quality": 0.9,
            "diversity": 0.4,
        }
        reward = calc.calculate(metrics)
        assert reward.total > 0
        assert reward.total <= 1.0

    def test_calculate_from_clips(self, sample_clips, sample_analyses):
        calc = RewardCalculator()
        quality = QualityScore(value=80.0)
        reward = calc.calculate_from_clips(
            sample_clips, sample_analyses, quality, target_duration=180.0
        )
        assert reward.total >= 0
        assert "retention" in reward.components
        assert "engagement" in reward.components

    def test_calculate_from_clips_empty(self):
        calc = RewardCalculator()
        reward = calc.calculate_from_clips([], [], QualityScore.zero())
        assert reward.total == 0.0

    def test_ablate(self):
        calc = RewardCalculator()
        ablated = calc.ablate("retention")
        assert "retention" not in ablated.weights
        # Weights should be renormalized
        assert abs(sum(ablated.weights.values()) - 1.0) < 0.01
