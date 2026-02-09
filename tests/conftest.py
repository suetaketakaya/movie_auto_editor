"""Shared test fixtures for all tests."""
from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.entities.content_type import ContentType
from backend.src.core.entities.experiment import Experiment, Trial
from backend.src.core.entities.project import Project, ProjectStatus
from backend.src.core.value_objects.quality_score import QualityScore
from backend.src.core.value_objects.reward_signal import RewardSignal
from backend.src.core.value_objects.time_range import TimeRange


# ── Frame Analysis Fixtures ────────────────────────────────────────────────

@pytest.fixture
def sample_frame_analysis() -> FrameAnalysis:
    return FrameAnalysis(
        frame_path="/tmp/frame_001.jpg",
        timestamp=10.0,
        kill_log=True,
        match_status="normal",
        action_intensity="high",
        enemy_visible=True,
        scene_description="Player getting a kill",
        confidence=0.9,
        excitement_score=25.0,
        model_used="qwen2-vl:7b",
    )


@pytest.fixture
def sample_analyses() -> list[FrameAnalysis]:
    return [
        FrameAnalysis(timestamp=5.0, kill_log=False, action_intensity="low", excitement_score=5.0),
        FrameAnalysis(timestamp=10.0, kill_log=True, action_intensity="high", excitement_score=25.0),
        FrameAnalysis(timestamp=15.0, kill_log=True, action_intensity="very_high", excitement_score=35.0),
        FrameAnalysis(timestamp=20.0, kill_log=False, action_intensity="medium", excitement_score=15.0),
        FrameAnalysis(timestamp=25.0, kill_log=True, action_intensity="high", excitement_score=30.0),
    ]


# ── Clip Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_clip() -> Clip:
    return Clip(
        time_range=TimeRange(start_seconds=10.0, end_seconds=18.0),
        reason="kill detected",
        score=QualityScore(value=85.0),
        clip_type="kill",
        label="KILL",
        priority=5,
        action_intensity="high",
    )


@pytest.fixture
def sample_clips() -> list[Clip]:
    return [
        Clip(
            time_range=TimeRange(start_seconds=5.0, end_seconds=12.0),
            clip_type="multi_kill",
            score=QualityScore(value=90.0),
            action_intensity="very_high",
        ),
        Clip(
            time_range=TimeRange(start_seconds=20.0, end_seconds=28.0),
            clip_type="clutch",
            score=QualityScore(value=80.0),
            action_intensity="high",
        ),
        Clip(
            time_range=TimeRange(start_seconds=35.0, end_seconds=42.0),
            clip_type="highlight",
            score=QualityScore(value=70.0),
            action_intensity="medium",
        ),
    ]


# ── Project Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def sample_project() -> Project:
    return Project(
        id="test-project-123",
        name="Test Project",
        input_video_path="/tmp/input.mp4",
        output_dir="/tmp/output",
        content_type=ContentType.FPS_MONTAGE,
        config={"target_duration": 180.0},
    )


# ── Experiment Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def sample_experiment() -> Experiment:
    return Experiment(
        id="test-exp-123",
        name="Test Experiment",
        parameter_space={"learning_rate": [0.01, 0.1], "batch_size": [16, 32, 64]},
        description="Test experiment for unit tests",
    )


@pytest.fixture
def sample_trial() -> Trial:
    return Trial(
        trial_num=1,
        parameters={"learning_rate": 0.05, "batch_size": 32},
        reward=RewardSignal(total=0.85, components={"retention": 0.9, "engagement": 0.8}),
        sub_metrics={"quality_score": 85.0},
    )


# ── Mock Port Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def mock_vision_port():
    mock = AsyncMock()
    mock.analyze_frames_batch.return_value = [
        FrameAnalysis(timestamp=5.0, kill_log=False, action_intensity="low"),
        FrameAnalysis(timestamp=10.0, kill_log=True, action_intensity="high"),
    ]
    return mock


@pytest.fixture
def mock_editor_port():
    mock = AsyncMock()
    mock.create_highlight.return_value = "/tmp/output/highlight.mp4"
    return mock


@pytest.fixture
def mock_audio_port():
    mock = AsyncMock()
    mock.normalize_audio.return_value = "/tmp/output/normalized.mp4"
    mock.add_background_music.return_value = "/tmp/output/with_bgm.mp4"
    return mock


@pytest.fixture
def mock_effects_port():
    mock = AsyncMock()
    mock.apply_color_grading.return_value = "/tmp/output/graded.mp4"
    return mock


@pytest.fixture
def mock_text_overlay_port():
    return AsyncMock()


@pytest.fixture
def mock_frame_extraction_port():
    mock = AsyncMock()
    mock.extract_frames.return_value = ["/tmp/frames/001.jpg", "/tmp/frames/002.jpg"]
    return mock


@pytest.fixture
def mock_project_repository():
    mock = AsyncMock()
    mock.save.return_value = None
    mock.get_by_id.return_value = None
    mock.list_all.return_value = []
    return mock


@pytest.fixture
def mock_notifier():
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_file_storage():
    mock = AsyncMock()
    mock.save_file.return_value = "/tmp/saved_file.mp4"
    return mock


@pytest.fixture
def mock_task_queue():
    mock = AsyncMock()
    mock.enqueue.return_value = "task-123"
    return mock


@pytest.fixture
def mock_metrics_store():
    mock = MagicMock()
    mock.start_run.return_value = "run-123"
    return mock


@pytest.fixture
def mock_experiment_repo():
    mock = AsyncMock()
    mock.save.return_value = None
    mock.get_by_id.return_value = None
    mock.list_all.return_value = []
    return mock
