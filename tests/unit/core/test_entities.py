"""Unit tests for core entities."""
from __future__ import annotations

import pytest
from datetime import datetime

from backend.src.core.entities.clip import Clip
from backend.src.core.entities.content_type import ContentType
from backend.src.core.entities.experiment import Experiment, ExperimentStatus, Trial
from backend.src.core.entities.project import Project, ProjectStatus
from backend.src.core.entities.timeline import Timeline
from backend.src.core.value_objects.quality_score import QualityScore
from backend.src.core.value_objects.reward_signal import RewardSignal
from backend.src.core.value_objects.time_range import TimeRange


class TestProject:
    """Tests for Project entity."""

    def test_creation_with_defaults(self):
        project = Project()
        assert project.id is not None
        assert project.status == ProjectStatus.UPLOADED
        assert project.progress == 0

    def test_creation_with_values(self):
        project = Project(
            id="test-123",
            name="My Project",
            input_video_path="/videos/input.mp4",
            output_dir="/videos/output",
            content_type=ContentType.FPS_MONTAGE,
        )
        assert project.id == "test-123"
        assert project.name == "My Project"
        assert project.content_type == ContentType.FPS_MONTAGE

    def test_start_processing(self):
        project = Project(id="test")
        project.start_processing()
        assert project.status == ProjectStatus.PROCESSING
        assert project.progress == 0

    def test_complete(self):
        project = Project(id="test")
        project.start_processing()
        project.complete(
            output_paths={"main": "/output/video.mp4"},
            result={"clips": [], "quality_score": 85.0},
        )
        assert project.status == ProjectStatus.COMPLETED
        assert project.progress == 100
        assert project.output_paths["main"] == "/output/video.mp4"
        assert project.result["quality_score"] == 85.0

    def test_fail(self):
        project = Project(id="test")
        project.start_processing()
        project.fail("Something went wrong")
        assert project.status == ProjectStatus.FAILED
        assert project.error == "Something went wrong"
        assert project.error_message == "Something went wrong"

    def test_cancel(self):
        project = Project(id="test")
        project.start_processing()
        project.cancel()
        assert project.status == ProjectStatus.CANCELLED
        assert project.error == "cancelled"

    def test_update_progress(self):
        project = Project(id="test")
        project.update_progress("analyzing", 50)
        assert project.current_stage == "analyzing"
        assert project.progress == 50

    def test_to_legacy_dict(self):
        project = Project(
            id="test-123",
            name="Test",
            filename="video.mp4",
            status=ProjectStatus.COMPLETED,
            progress=100,
        )
        legacy = project.to_legacy_dict()
        assert legacy["id"] == "test-123"
        assert legacy["status"] == "completed"
        assert legacy["progress"] == 100


class TestClip:
    """Tests for Clip entity."""

    def test_creation(self):
        clip = Clip(
            time_range=TimeRange(start_seconds=10.0, end_seconds=20.0),
            reason="kill detected",
            score=QualityScore(value=80.0),
            clip_type="kill",
        )
        assert clip.duration == 10.0
        assert clip.start == 10.0
        assert clip.end == 20.0

    def test_with_adjusted_range(self):
        clip = Clip(
            time_range=TimeRange(start_seconds=10.0, end_seconds=20.0),
            clip_type="kill",
            score=QualityScore(value=85.0),
        )
        new_range = TimeRange(start_seconds=8.0, end_seconds=22.0)
        adjusted = clip.with_adjusted_range(new_range)
        assert adjusted.start == 8.0
        assert adjusted.end == 22.0
        assert adjusted.score.value == 85.0  # Preserved

    def test_with_score(self):
        clip = Clip(
            time_range=TimeRange(start_seconds=10.0, end_seconds=20.0),
            score=QualityScore(value=70.0),
        )
        new_score = QualityScore(value=90.0)
        updated = clip.with_score(new_score)
        assert updated.score.value == 90.0
        assert updated.duration == 10.0  # Preserved

    def test_to_legacy_dict(self):
        clip = Clip(
            time_range=TimeRange(start_seconds=10.0, end_seconds=20.0),
            reason="test",
            score=QualityScore(value=80.0),
            clip_type="highlight",
            label="HIGHLIGHT",
            priority=5,
            action_intensity="high",
        )
        legacy = clip.to_legacy_dict()
        assert legacy["start"] == 10.0
        assert legacy["end"] == 20.0
        assert legacy["type"] == "highlight"
        assert legacy["score"] == 80.0

    def test_from_legacy_dict(self):
        data = {
            "start": 5.0,
            "end": 15.0,
            "reason": "multi kill",
            "score": 90.0,
            "type": "multi_kill",
        }
        clip = Clip.from_legacy_dict(data)
        assert clip.start == 5.0
        assert clip.end == 15.0
        assert clip.score.value == 90.0


class TestTimeline:
    """Tests for Timeline entity."""

    def test_creation(self):
        timeline = Timeline(target_duration=180.0)
        assert timeline.clip_count == 0
        assert timeline.total_duration == 0.0

    def test_add_clip(self):
        timeline = Timeline()
        clip = Clip(time_range=TimeRange(start_seconds=0.0, end_seconds=10.0))
        timeline.add_clip(clip)
        assert timeline.clip_count == 1
        assert timeline.total_duration == 10.0

    def test_remove_clip(self):
        timeline = Timeline()
        clip = Clip(
            id="clip-1",
            time_range=TimeRange(start_seconds=0.0, end_seconds=10.0),
        )
        timeline.add_clip(clip)
        timeline.remove_clip("clip-1")
        assert timeline.clip_count == 0

    def test_reorder_by_score(self):
        timeline = Timeline()
        timeline.add_clip(Clip(
            time_range=TimeRange(0.0, 5.0),
            score=QualityScore(value=50.0),
        ))
        timeline.add_clip(Clip(
            time_range=TimeRange(5.0, 10.0),
            score=QualityScore(value=90.0),
        ))
        timeline.add_clip(Clip(
            time_range=TimeRange(10.0, 15.0),
            score=QualityScore(value=70.0),
        ))
        timeline.reorder_by_score()
        assert timeline.clips[0].score.value == 90.0
        assert timeline.clips[1].score.value == 70.0
        assert timeline.clips[2].score.value == 50.0

    def test_average_clip_duration(self):
        timeline = Timeline()
        timeline.add_clip(Clip(time_range=TimeRange(0.0, 10.0)))
        timeline.add_clip(Clip(time_range=TimeRange(10.0, 20.0)))
        assert timeline.average_clip_duration == 10.0

    def test_has_hook(self):
        timeline = Timeline()
        clip_no_hook = Clip(time_range=TimeRange(0.0, 5.0))
        timeline.add_clip(clip_no_hook)
        assert timeline.has_hook is False

        clip_hook = Clip(
            time_range=TimeRange(0.0, 3.0),
            metadata={"is_hook": True},
        )
        timeline.clips[0] = clip_hook
        assert timeline.has_hook is True


class TestExperiment:
    """Tests for Experiment entity."""

    def test_creation(self):
        exp = Experiment(
            name="Test Exp",
            parameter_space={"lr": [0.01, 0.1]},
        )
        assert exp.id is not None
        assert exp.status == ExperimentStatus.CREATED
        assert len(exp.trials) == 0

    def test_add_trial(self):
        exp = Experiment(name="Test")
        trial = Trial(
            trial_num=1,
            parameters={"lr": 0.05},
            reward=RewardSignal(total=0.8),
        )
        exp.add_trial(trial)
        assert len(exp.trials) == 1
        assert exp.best_trial == trial

    def test_best_trial_tracking(self):
        exp = Experiment(name="Test")
        trial1 = Trial(trial_num=1, reward=RewardSignal(total=0.5))
        trial2 = Trial(trial_num=2, reward=RewardSignal(total=0.8))
        trial3 = Trial(trial_num=3, reward=RewardSignal(total=0.6))

        exp.add_trial(trial1)
        assert exp.best_trial.trial_num == 1

        exp.add_trial(trial2)
        assert exp.best_trial.trial_num == 2

        exp.add_trial(trial3)
        assert exp.best_trial.trial_num == 2  # Still trial2
