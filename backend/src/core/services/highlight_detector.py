"""
Highlight detection and excitement analysis - pure domain logic.
Extracted from legacy advanced_analyzer.py. Generalized from FPS-specific to universal.
"""
from __future__ import annotations

import statistics

from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.value_objects.quality_score import QualityScore
from backend.src.core.value_objects.time_range import TimeRange


class HighlightDetector:
    """Detects highlights, multi-events, clutch moments, and excitement levels."""

    def analyze_excitement_levels(self, analyses: list[FrameAnalysis]) -> list[FrameAnalysis]:
        """Calculate excitement scores for each frame analysis."""
        enhanced: list[FrameAnalysis] = []
        for a in analyses:
            excitement = 0.0
            if a.kill_log:
                excitement += 20
            intensity_map = {"very_high": 15, "high": 10, "medium": 5, "low": 0}
            excitement += intensity_map.get(a.action_intensity, 0)
            status_map = {"victory": 10, "clutch": 15, "defeat": -5, "normal": 0}
            excitement += status_map.get(a.match_status, 0)

            updated = FrameAnalysis(
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
            )
            enhanced.append(updated)
        return enhanced

    def detect_multi_events(
        self, analyses: list[FrameAnalysis], time_window: float = 10.0
    ) -> list[dict]:
        """Detect rapid successive events (multi-kills, rapid goals, etc)."""
        kill_timestamps = sorted(a.timestamp for a in analyses if a.kill_log)
        if not kill_timestamps:
            return []

        multi_events: list[dict] = []
        i = 0
        while i < len(kill_timestamps):
            window_start = kill_timestamps[i]
            count = 1
            j = i + 1
            while j < len(kill_timestamps) and kill_timestamps[j] - window_start <= time_window:
                count += 1
                j += 1

            if count >= 2:
                event_type = self._classify_multi_event(count)
                multi_events.append({
                    "type": event_type,
                    "timestamp": window_start,
                    "kill_count": count,
                    "end_timestamp": kill_timestamps[j - 1] if j > i else window_start,
                })
            i = j if j > i else i + 1

        return multi_events

    def _classify_multi_event(self, count: int) -> str:
        if count >= 5:
            return "ACE"
        if count == 4:
            return "QUAD KILL"
        if count == 3:
            return "TRIPLE KILL"
        if count == 2:
            return "DOUBLE KILL"
        return "KILL"

    def detect_clutch_moments(self, analyses: list[FrameAnalysis]) -> list[dict]:
        """Detect clutch/critical moments."""
        return [
            {
                "timestamp": a.timestamp,
                "type": "clutch",
                "action_intensity": a.action_intensity,
            }
            for a in analyses
            if a.match_status == "clutch"
        ]

    def analyze_momentum_shifts(self, analyses: list[FrameAnalysis]) -> list[dict]:
        """Detect momentum shifts using moving average of excitement."""
        timeline = [
            (a.timestamp, a.excitement_score)
            for a in analyses
            if a.excitement_score > 0
        ]
        if len(timeline) < 10:
            return []

        shifts: list[dict] = []
        window = 5
        for i in range(len(timeline) - window * 2):
            before = [x[1] for x in timeline[i : i + window]]
            after = [x[1] for x in timeline[i + window : i + window * 2]]
            if len(after) < window:
                break
            avg_before = statistics.mean(before)
            avg_after = statistics.mean(after)
            change = avg_after - avg_before
            if abs(change) > 10:
                shifts.append({
                    "timestamp": timeline[i + window][0],
                    "type": "momentum_up" if change > 0 else "momentum_down",
                    "magnitude": abs(change),
                })
        return shifts

    def suggest_highlights(
        self,
        analyses: list[FrameAnalysis],
        multi_events: list[dict],
        clutch_moments: list[dict],
    ) -> list[Clip]:
        """Suggest highlight clips from detected patterns."""
        highlights: list[Clip] = []

        for mk in multi_events:
            end_ts = mk.get("end_timestamp", mk["timestamp"])
            highlights.append(Clip(
                time_range=TimeRange(max(0, mk["timestamp"] - 3), end_ts + 3),
                clip_type="multi_kill",
                label=mk["type"],
                priority=10,
                reason=f"{mk['type']} ({mk['kill_count']} kills)",
                score=QualityScore(value=90),
            ))

        for cm in clutch_moments:
            highlights.append(Clip(
                time_range=TimeRange(max(0, cm["timestamp"] - 5), cm["timestamp"] + 5),
                clip_type="clutch",
                label="CLUTCH",
                priority=9,
                reason="Clutch moment",
                score=QualityScore(value=80),
            ))

        for a in analyses:
            if a.excitement_score >= 25:
                highlights.append(Clip(
                    time_range=TimeRange(max(0, a.timestamp - 2), a.timestamp + 3),
                    clip_type="high_excitement",
                    label="INTENSE",
                    priority=7,
                    reason="High excitement",
                    score=QualityScore(value=70),
                ))

        highlights.sort(key=lambda c: c.priority, reverse=True)
        return self.merge_overlapping_clips(highlights)

    def merge_overlapping_clips(self, clips: list[Clip]) -> list[Clip]:
        """Merge overlapping clips, keeping highest priority."""
        if not clips:
            return []
        sorted_clips = sorted(clips, key=lambda c: c.start)
        merged = [sorted_clips[0]]

        for current in sorted_clips[1:]:
            last = merged[-1]
            if current.start <= last.end:
                new_range = TimeRange(
                    min(last.start, current.start),
                    max(last.end, current.end),
                )
                keep = last if last.priority >= current.priority else current
                merged[-1] = keep.with_adjusted_range(new_range)
            else:
                merged.append(current)
        return merged

    def analyze_variety(self, clips: list[Clip]) -> dict:
        """Analyze variety of clip types and durations."""
        if not clips:
            return {"variety_score": 0, "issues": ["no_clips"]}

        types = [c.clip_type or "unknown" for c in clips]
        unique_types = len(set(types))
        durations = [c.duration for c in clips]
        dur_variance = statistics.variance(durations) if len(durations) > 1 else 0

        variety_score = min(100, unique_types * 20 + min(30, dur_variance * 5))
        issues: list[str] = []
        if unique_types < 2:
            issues.append("low_type_variety")
        if dur_variance < 2:
            issues.append("uniform_clip_lengths")

        return {
            "variety_score": variety_score,
            "unique_types": unique_types,
            "duration_variance": dur_variance,
            "issues": issues,
        }
