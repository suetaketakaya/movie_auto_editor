"""Unit tests for CreativeDirector."""
from __future__ import annotations

import pytest

from backend.src.application.creative_director import CreativeDirector, DirectorDecisions
from backend.src.application.plugins.base_content_plugin import DirectorConfig
from backend.src.core.entities.analysis_result import FrameAnalysis


class TestCreativeDirector:
    """Tests for CreativeDirector."""

    @pytest.fixture
    def director(self):
        return CreativeDirector()

    @pytest.fixture
    def director_with_config(self):
        config = DirectorConfig(
            target_duration=120.0,
            min_clip_length=2.0,
            max_clip_length=10.0,
        )
        return CreativeDirector(config=config)

    @pytest.fixture
    def rich_analyses(self):
        """Analyses with varied content for testing full pipeline."""
        return [
            FrameAnalysis(timestamp=5.0, kill_log=False, action_intensity="low", match_status="normal"),
            FrameAnalysis(timestamp=10.0, kill_log=True, action_intensity="high", match_status="normal"),
            FrameAnalysis(timestamp=12.0, kill_log=True, action_intensity="very_high", match_status="normal"),
            FrameAnalysis(timestamp=20.0, kill_log=False, action_intensity="medium", match_status="clutch"),
            FrameAnalysis(timestamp=30.0, kill_log=True, action_intensity="high", match_status="normal"),
            FrameAnalysis(timestamp=40.0, kill_log=False, action_intensity="low", match_status="normal"),
            FrameAnalysis(timestamp=50.0, kill_log=True, action_intensity="very_high", match_status="victory"),
        ]

    def test_direct_returns_decisions(self, director, rich_analyses):
        decisions = director.direct(rich_analyses)

        assert isinstance(decisions, DirectorDecisions)
        assert isinstance(decisions.clips, list)
        assert isinstance(decisions.engagement_curve, dict)
        assert isinstance(decisions.variety_analysis, dict)
        assert isinstance(decisions.suggestions, list)
        assert isinstance(decisions.multi_events, list)

    def test_direct_detects_multi_events(self, director, rich_analyses):
        decisions = director.direct(rich_analyses)

        # Should detect double kill at timestamps 10, 12
        assert len(decisions.multi_events) > 0

    def test_direct_detects_clutch_moments(self, director, rich_analyses):
        decisions = director.direct(rich_analyses)

        # Should detect clutch at timestamp 20
        assert len(decisions.clutch_moments) > 0

    def test_direct_creates_clips(self, director, rich_analyses):
        decisions = director.direct(rich_analyses)

        # Should create clips from the exciting moments
        assert len(decisions.clips) > 0

    def test_direct_with_config(self, director_with_config, rich_analyses):
        decisions = director_with_config.direct(rich_analyses)

        assert isinstance(decisions, DirectorDecisions)
        # Clips should respect max duration
        for clip in decisions.clips:
            assert clip.duration <= 10.0

    def test_direct_empty_analyses(self, director):
        decisions = director.direct([])

        assert decisions.clips == []
        assert decisions.multi_events == []
        assert decisions.clutch_moments == []

    def test_direct_no_kills(self, director):
        analyses = [
            FrameAnalysis(timestamp=10.0, kill_log=False, action_intensity="low"),
            FrameAnalysis(timestamp=20.0, kill_log=False, action_intensity="low"),
        ]

        decisions = director.direct(analyses)

        # Should have no multi-kill events
        assert len(decisions.multi_events) == 0

    def test_engagement_curve_structure(self, director, rich_analyses):
        decisions = director.direct(rich_analyses)

        curve = decisions.engagement_curve
        if decisions.clips:  # Only check if clips were generated
            assert "avg_score" in curve
            assert "clip_count" in curve

    def test_variety_analysis_structure(self, director, rich_analyses):
        decisions = director.direct(rich_analyses)

        variety = decisions.variety_analysis
        assert "variety_score" in variety

    def test_momentum_shifts_detection(self, director):
        # Create analyses with clear momentum shift
        analyses = []
        # Low excitement period
        for i in range(10):
            analyses.append(FrameAnalysis(
                timestamp=float(i * 2),
                kill_log=False,
                action_intensity="low",
                excitement_score=5.0,
            ))
        # High excitement period
        for i in range(10, 20):
            analyses.append(FrameAnalysis(
                timestamp=float(i * 2),
                kill_log=True,
                action_intensity="very_high",
                excitement_score=35.0,
            ))

        decisions = director.direct(analyses)

        assert isinstance(decisions.momentum_shifts, list)


class TestDirectorDecisions:
    """Tests for DirectorDecisions dataclass."""

    def test_default_values(self):
        decisions = DirectorDecisions()

        assert decisions.clips == []
        assert decisions.hook_clip is None
        assert decisions.engagement_curve == {}
        assert decisions.variety_analysis == {}
        assert decisions.suggestions == []
        assert decisions.multi_events == []
        assert decisions.clutch_moments == []
        assert decisions.momentum_shifts == []
