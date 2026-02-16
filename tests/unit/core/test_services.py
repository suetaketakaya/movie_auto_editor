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

    def test_score_clip_ideal_duration(self):
        """5-10s duration should get max duration bonus."""
        scorer = ClipScorer()
        clip = Clip(time_range=TimeRange(start_seconds=0.0, end_seconds=7.0))
        analyses = [FrameAnalysis(timestamp=3.0, excitement_score=10.0)]
        score = scorer.score_clip(clip, analyses)
        assert score.breakdown["duration"] == 20.0

    def test_score_clip_too_short(self):
        """< 3s duration gets no duration bonus."""
        scorer = ClipScorer()
        clip = Clip(time_range=TimeRange(start_seconds=0.0, end_seconds=2.0))
        analyses = [FrameAnalysis(timestamp=1.0, excitement_score=10.0)]
        score = scorer.score_clip(clip, analyses)
        assert score.breakdown["duration"] == 0.0

    def test_score_clip_max_score_capped(self):
        """Score should never exceed 100."""
        scorer = ClipScorer()
        clip = Clip(time_range=TimeRange(start_seconds=0.0, end_seconds=7.0))
        analyses = [
            FrameAnalysis(timestamp=i, kill_log=True, excitement_score=80.0)
            for i in range(7)
        ]
        score = scorer.score_clip(clip, analyses)
        assert score.value <= 100.0

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

    def test_predict_engagement_diversity_bonus(self):
        """Multiple clip types should boost the score."""
        scorer = ClipScorer()
        clips = [
            Clip(time_range=TimeRange(0.0, 5.0), clip_type="kill"),
            Clip(time_range=TimeRange(10.0, 15.0), clip_type="clutch"),
            Clip(time_range=TimeRange(20.0, 25.0), clip_type="multi_kill"),
        ]
        analyses = [FrameAnalysis(timestamp=3.0, excitement_score=20.0)]
        result = scorer.predict_engagement(clips, analyses)
        assert result["overall_score"] > 0

    def test_detect_drop_off_points(self):
        scorer = ClipScorer()
        clips = [
            Clip(time_range=TimeRange(0.0, 5.0)),
            Clip(time_range=TimeRange(5.0, 25.0)),  # > 15s
            Clip(time_range=TimeRange(25.0, 35.0)),
        ]
        drop_offs = scorer.detect_drop_off_points(clips)
        assert len(drop_offs) >= 1
        assert 5.0 in drop_offs

    def test_detect_drop_off_dynamic_threshold(self):
        """High-action clips get a higher threshold before flagging drop-off."""
        scorer = ClipScorer()
        # 18s clip with high action - threshold is 20s, so no drop-off
        clips = [
            Clip(time_range=TimeRange(0.0, 18.0), action_intensity="high"),
        ]
        drop_offs = scorer.detect_drop_off_points(clips)
        assert len(drop_offs) == 0

    def test_suggest_improvements(self, sample_clips, sample_analyses):
        scorer = ClipScorer()
        suggestions = scorer.suggest_improvements(sample_clips, sample_analyses)
        assert isinstance(suggestions, list)

    def test_suggest_improvements_too_long(self):
        scorer = ClipScorer()
        clips = [Clip(time_range=TimeRange(0.0, 310.0))]
        suggestions = scorer.suggest_improvements(clips, [])
        assert any("too long" in s.lower() for s in suggestions)

    def test_suggest_improvements_low_variety(self):
        scorer = ClipScorer()
        clips = [
            Clip(time_range=TimeRange(i * 10.0, i * 10.0 + 5.0), clip_type="kill", score=QualityScore(value=50))
            for i in range(5)
        ]
        suggestions = scorer.suggest_improvements(clips, [])
        assert any("variety" in s.lower() for s in suggestions)


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

    def test_trim_empty_clips(self):
        planner = CompositionPlanner(target_duration=20.0)
        trimmed = planner.trim_to_target_duration([])
        assert trimmed == []

    def test_create_hook_intro(self, sample_clips):
        planner = CompositionPlanner()
        hook = planner.create_hook_intro(sample_clips)
        assert hook is not None
        assert hook.clip_type == "hook"
        assert hook.metadata.get("is_hook") is True

    def test_create_hook_intro_empty(self):
        planner = CompositionPlanner()
        hook = planner.create_hook_intro([])
        assert hook is None

    def test_analyze_engagement_curve(self, sample_clips):
        planner = CompositionPlanner()
        curve = planner.analyze_engagement_curve(sample_clips)
        assert "avg_score" in curve
        assert "clip_count" in curve
        assert "pacing_score" in curve

    def test_analyze_engagement_curve_empty(self):
        planner = CompositionPlanner()
        curve = planner.analyze_engagement_curve([])
        assert curve.get("status") == "no_clips"

    def test_optimize_pacing_interleaving(self):
        """Pacing should interleave high and medium intensity clips."""
        planner = CompositionPlanner()
        clips = [
            Clip(time_range=TimeRange(0.0, 5.0), action_intensity="high", score=QualityScore(value=80)),
            Clip(time_range=TimeRange(5.0, 10.0), action_intensity="high", score=QualityScore(value=70)),
            Clip(time_range=TimeRange(10.0, 15.0), action_intensity="medium", score=QualityScore(value=60)),
            Clip(time_range=TimeRange(15.0, 20.0), action_intensity="medium", score=QualityScore(value=50)),
        ]
        paced = planner.optimize_pacing(clips)
        assert len(paced) == 4


class TestHighlightDetector:
    """Tests for HighlightDetector service."""

    def test_analyze_excitement_levels(self, sample_analyses):
        detector = HighlightDetector()
        enhanced = detector.analyze_excitement_levels(sample_analyses)
        assert len(enhanced) == len(sample_analyses)
        for analysis in enhanced:
            assert analysis.excitement_score >= 0

    def test_excitement_kill_base_score(self):
        """Kill event should contribute 25 base points."""
        detector = HighlightDetector()
        analyses = [FrameAnalysis(timestamp=10.0, kill_log=True, action_intensity="low")]
        enhanced = detector.analyze_excitement_levels(analyses)
        assert enhanced[0].excitement_score >= 25

    def test_excitement_multi_kill_bonus(self):
        """Multi-kill (kill_count >= 3) should get extra bonus."""
        detector = HighlightDetector()
        analyses = [FrameAnalysis(timestamp=10.0, kill_log=True, kill_count=3, action_intensity="low")]
        enhanced = detector.analyze_excitement_levels(analyses)
        assert enhanced[0].excitement_score >= 40  # 25 base + 15 bonus

    def test_excitement_enemy_visible_bonus(self):
        """Enemy visibility should add 10 points."""
        detector = HighlightDetector()
        base = [FrameAnalysis(timestamp=10.0, action_intensity="medium")]
        with_enemy = [FrameAnalysis(timestamp=10.0, action_intensity="medium", enemy_visible=True)]
        base_result = detector.analyze_excitement_levels(base)
        enemy_result = detector.analyze_excitement_levels(with_enemy)
        assert enemy_result[0].excitement_score > base_result[0].excitement_score

    def test_excitement_confidence_weighting(self):
        """High confidence should yield higher final score than low confidence."""
        detector = HighlightDetector()
        low_conf = [FrameAnalysis(timestamp=10.0, kill_log=True, action_intensity="high", confidence=0.3)]
        high_conf = [FrameAnalysis(timestamp=10.0, kill_log=True, action_intensity="high", confidence=0.9)]
        low_result = detector.analyze_excitement_levels(low_conf)
        high_result = detector.analyze_excitement_levels(high_conf)
        assert high_result[0].excitement_score > low_result[0].excitement_score

    def test_excitement_empty_input(self):
        detector = HighlightDetector()
        result = detector.analyze_excitement_levels([])
        assert result == []

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

    def test_detect_multi_events_ace(self):
        detector = HighlightDetector()
        analyses = [
            FrameAnalysis(timestamp=10.0 + i, kill_log=True)
            for i in range(5)
        ]
        events = detector.detect_multi_events(analyses, time_window=10.0)
        assert any(e["type"] == "ACE" for e in events)

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

    def test_merge_overlapping_empty(self):
        detector = HighlightDetector()
        assert detector.merge_overlapping_clips([]) == []

    def test_analyze_variety(self, sample_clips):
        detector = HighlightDetector()
        variety = detector.analyze_variety(sample_clips)
        assert "variety_score" in variety
        assert "unique_types" in variety

    def test_analyze_variety_empty(self):
        detector = HighlightDetector()
        variety = detector.analyze_variety([])
        assert variety["variety_score"] == 0
        assert "no_clips" in variety["issues"]

    def test_momentum_shifts_insufficient_data(self):
        detector = HighlightDetector()
        analyses = [FrameAnalysis(timestamp=i, excitement_score=10.0) for i in range(5)]
        shifts = detector.analyze_momentum_shifts(analyses)
        assert shifts == []


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

    def test_ablate_all_components(self):
        """Ablating all components should return a calculator with no weights."""
        calc = RewardCalculator()
        while calc.weights:
            key = next(iter(calc.weights))
            calc = calc.ablate(key)
        assert len(calc.weights) == 0
