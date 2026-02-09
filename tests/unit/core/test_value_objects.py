"""Unit tests for core value objects."""
from __future__ import annotations

import pytest

from backend.src.core.value_objects.quality_score import QualityScore
from backend.src.core.value_objects.reward_signal import RewardSignal
from backend.src.core.value_objects.time_range import TimeRange
from backend.src.core.value_objects.effect_spec import EffectSpec, EffectType


class TestTimeRange:
    """Tests for TimeRange value object."""

    def test_creation(self):
        tr = TimeRange(start_seconds=10.0, end_seconds=20.0)
        assert tr.start_seconds == 10.0
        assert tr.end_seconds == 20.0

    def test_duration(self):
        tr = TimeRange(start_seconds=5.0, end_seconds=15.0)
        assert tr.duration == 10.0

    def test_midpoint(self):
        tr = TimeRange(start_seconds=10.0, end_seconds=20.0)
        assert tr.midpoint == 15.0

    def test_negative_start_clamped_to_zero(self):
        tr = TimeRange(start_seconds=-5.0, end_seconds=10.0)
        assert tr.start_seconds == 0.0

    def test_invalid_end_before_start_raises(self):
        with pytest.raises(ValueError):
            TimeRange(start_seconds=20.0, end_seconds=10.0)

    def test_overlaps_true(self):
        tr1 = TimeRange(start_seconds=10.0, end_seconds=20.0)
        tr2 = TimeRange(start_seconds=15.0, end_seconds=25.0)
        assert tr1.overlaps(tr2) is True
        assert tr2.overlaps(tr1) is True

    def test_overlaps_false(self):
        tr1 = TimeRange(start_seconds=10.0, end_seconds=20.0)
        tr2 = TimeRange(start_seconds=25.0, end_seconds=35.0)
        assert tr1.overlaps(tr2) is False

    def test_merge(self):
        tr1 = TimeRange(start_seconds=10.0, end_seconds=20.0)
        tr2 = TimeRange(start_seconds=15.0, end_seconds=25.0)
        merged = tr1.merge(tr2)
        assert merged.start_seconds == 10.0
        assert merged.end_seconds == 25.0

    def test_merge_non_overlapping_raises(self):
        tr1 = TimeRange(start_seconds=10.0, end_seconds=20.0)
        tr2 = TimeRange(start_seconds=25.0, end_seconds=35.0)
        with pytest.raises(ValueError):
            tr1.merge(tr2)

    def test_split(self):
        tr = TimeRange(start_seconds=10.0, end_seconds=30.0)
        left, right = tr.split(at_seconds=20.0)
        assert left.start_seconds == 10.0
        assert left.end_seconds == 20.0
        assert right.start_seconds == 20.0
        assert right.end_seconds == 30.0

    def test_split_outside_range_raises(self):
        tr = TimeRange(start_seconds=10.0, end_seconds=20.0)
        with pytest.raises(ValueError):
            tr.split(at_seconds=25.0)

    def test_contains(self):
        tr = TimeRange(start_seconds=10.0, end_seconds=20.0)
        assert tr.contains(15.0) is True
        assert tr.contains(10.0) is True
        assert tr.contains(20.0) is True
        assert tr.contains(5.0) is False

    def test_extend(self):
        tr = TimeRange(start_seconds=10.0, end_seconds=20.0)
        extended = tr.extend(before=2.0, after=3.0)
        assert extended.start_seconds == 8.0
        assert extended.end_seconds == 23.0


class TestQualityScore:
    """Tests for QualityScore value object."""

    def test_creation(self):
        qs = QualityScore(value=85.0)
        assert qs.value == 85.0

    def test_clamped_above_100(self):
        qs = QualityScore(value=150.0)
        assert qs.value == 100.0

    def test_clamped_below_0(self):
        qs = QualityScore(value=-10.0)
        assert qs.value == 0.0

    def test_grade_a(self):
        qs = QualityScore(value=95.0)
        assert qs.grade == "A"

    def test_grade_b(self):
        qs = QualityScore(value=85.0)
        assert qs.grade == "B"

    def test_grade_c(self):
        qs = QualityScore(value=75.0)
        assert qs.grade == "C"

    def test_grade_d(self):
        qs = QualityScore(value=65.0)
        assert qs.grade == "D"

    def test_grade_f(self):
        qs = QualityScore(value=50.0)
        assert qs.grade == "F"

    def test_is_acceptable(self):
        assert QualityScore(value=75.0).is_acceptable is True
        assert QualityScore(value=65.0).is_acceptable is False

    def test_from_components(self):
        weights = {"action": 0.5, "pacing": 0.5}
        scores = {"action": 80.0, "pacing": 60.0}
        qs = QualityScore.from_components(weights, scores)
        assert qs.value == 70.0

    def test_with_bonus(self):
        qs = QualityScore(value=70.0, breakdown={"base": 70.0})
        qs2 = qs.with_bonus(10.0, "multi_kill")
        assert qs2.value == 80.0
        assert "multi_kill" in qs2.breakdown
        assert qs2.breakdown["multi_kill"] == 10.0

    def test_zero(self):
        qs = QualityScore.zero()
        assert qs.value == 0.0

    def test_perfect(self):
        qs = QualityScore.perfect()
        assert qs.value == 100.0


class TestRewardSignal:
    """Tests for RewardSignal value object."""

    def test_creation(self):
        rs = RewardSignal(total=0.75, components={"retention": 0.8, "ctr": 0.7})
        assert rs.total == 0.75
        assert rs.components["retention"] == 0.8

    def test_is_positive(self):
        assert RewardSignal(total=0.5).is_positive is True
        assert RewardSignal(total=-0.1).is_positive is False
        assert RewardSignal(total=0.0).is_positive is False

    def test_dominant_component(self):
        rs = RewardSignal(total=0.6, components={"a": 0.3, "b": 0.8, "c": 0.5})
        assert rs.dominant_component == "b"

    def test_dominant_component_empty(self):
        rs = RewardSignal(total=0.0, components={})
        assert rs.dominant_component is None

    def test_compute(self):
        components = {"retention": 0.8, "ctr": 0.6}
        weights = {"retention": 0.6, "ctr": 0.4}
        rs = RewardSignal.compute(components, weights)
        # 0.8 * 0.6 + 0.6 * 0.4 = 0.48 + 0.24 = 0.72
        assert abs(rs.total - 0.72) < 0.01

    def test_reweight(self):
        rs = RewardSignal(total=0.7, components={"a": 0.8, "b": 0.6}, weights={"a": 0.5, "b": 0.5})
        new_rs = rs.reweight({"a": 0.8, "b": 0.2})
        # Normalized: a=0.8, b=0.2 -> 0.8*0.8 + 0.2*0.6 = 0.64 + 0.12 = 0.76
        assert abs(new_rs.total - 0.76) < 0.01

    def test_without_component(self):
        rs = RewardSignal(
            total=0.7,
            components={"a": 0.8, "b": 0.6, "c": 0.5},
            weights={"a": 0.4, "b": 0.3, "c": 0.3},
        )
        rs2 = rs.without_component("c")
        assert "c" not in rs2.components
        assert "c" not in rs2.weights


class TestEffectSpec:
    """Tests for EffectSpec value object."""

    def test_creation(self):
        spec = EffectSpec(
            effect_type=EffectType.COLOR_GRADING,
            parameters={"preset": "cinematic"},
        )
        assert spec.effect_type == EffectType.COLOR_GRADING
        assert spec.parameters["preset"] == "cinematic"

    def test_effect_type_enum_values(self):
        assert EffectType.COLOR_GRADING.value == "color_grading"
        assert EffectType.SLOW_MOTION.value == "slow_motion"
        assert EffectType.ZOOM.value == "zoom"
        assert EffectType.TRANSITION.value == "transition"

    def test_with_time_range(self):
        tr = TimeRange(start_seconds=10.0, end_seconds=15.0)
        spec = EffectSpec(
            effect_type=EffectType.SLOW_MOTION,
            parameters={"speed": 0.5},
            time_range=tr,
        )
        assert spec.time_range is not None
        assert spec.time_range.duration == 5.0
