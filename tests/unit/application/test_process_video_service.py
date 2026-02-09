"""Unit tests for ProcessVideoService."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.src.application.dto.process_request import ProcessRequest
from backend.src.application.dto.process_result import ProcessResult
from backend.src.application.process_video_service import ProcessVideoService
from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.content_type import ContentType


class TestProcessVideoService:
    """Tests for ProcessVideoService."""

    @pytest.fixture
    def service(
        self,
        mock_vision_port,
        mock_editor_port,
        mock_audio_port,
        mock_effects_port,
        mock_text_overlay_port,
        mock_frame_extraction_port,
        mock_project_repository,
        mock_notifier,
    ):
        return ProcessVideoService(
            vision=mock_vision_port,
            editor=mock_editor_port,
            audio=mock_audio_port,
            effects=mock_effects_port,
            text_overlay=mock_text_overlay_port,
            frame_extraction=mock_frame_extraction_port,
            repository=mock_project_repository,
            notifier=mock_notifier,
        )

    @pytest.fixture
    def sample_request(self):
        return ProcessRequest(
            project_id="test-project-123",
            project_name="Test Video",
            input_video_path="/tmp/input.mp4",
            output_dir="/tmp/output",
            content_type=ContentType.FPS_MONTAGE,
            config={"interval_seconds": 2.0},
        )

    @pytest.mark.asyncio
    async def test_execute_happy_path(
        self,
        service,
        sample_request,
        mock_vision_port,
        mock_editor_port,
        mock_project_repository,
        mock_notifier,
    ):
        # Setup mock to return analyses with enough excitement
        mock_vision_port.analyze_frames_batch.return_value = [
            FrameAnalysis(timestamp=5.0, kill_log=True, action_intensity="high", excitement_score=30.0),
            FrameAnalysis(timestamp=10.0, kill_log=True, action_intensity="very_high", excitement_score=40.0),
            FrameAnalysis(timestamp=15.0, kill_log=False, action_intensity="medium", excitement_score=15.0),
        ]

        result = await service.execute(sample_request)

        assert result.project_id == "test-project-123"
        # Repository should be called multiple times (start, progress updates, complete)
        assert mock_project_repository.save.called
        # Notifier should send completion
        assert mock_notifier.send_completion.called or mock_notifier.send_progress.called

    @pytest.mark.asyncio
    async def test_execute_no_clips_returns_empty_result(
        self,
        service,
        sample_request,
        mock_vision_port,
    ):
        # Return analyses with no exciting content
        mock_vision_port.analyze_frames_batch.return_value = [
            FrameAnalysis(timestamp=5.0, kill_log=False, action_intensity="low", excitement_score=5.0),
        ]

        result = await service.execute(sample_request)

        assert result.project_id == "test-project-123"
        assert result.clips == []
        assert result.quality_score == 0.0

    @pytest.mark.asyncio
    async def test_execute_failure_notifies_error(
        self,
        service,
        sample_request,
        mock_vision_port,
        mock_project_repository,
        mock_notifier,
    ):
        # Make vision analysis fail
        mock_vision_port.analyze_frames_batch.side_effect = RuntimeError("Vision API error")

        with pytest.raises(RuntimeError, match="Vision API error"):
            await service.execute(sample_request)

        # Should notify error
        mock_notifier.send_error.assert_called()

    @pytest.mark.asyncio
    async def test_notify_sends_progress(
        self,
        service,
        sample_request,
        mock_project_repository,
        mock_notifier,
        mock_vision_port,
    ):
        mock_vision_port.analyze_frames_batch.return_value = [
            FrameAnalysis(timestamp=10.0, kill_log=True, excitement_score=30.0),
        ]

        await service.execute(sample_request)

        # Verify progress notifications were sent
        assert mock_notifier.send_progress.called

    def test_evaluate_quality(self, service):
        from backend.src.application.creative_director import DirectorDecisions

        decisions = DirectorDecisions(
            clips=[],
            engagement_curve={"avg_score": 50.0, "pacing_score": 60.0},
            variety_analysis={"variety_score": 40.0},
        )
        analyses = []

        quality = service._evaluate_quality(decisions, analyses)

        # 50*0.4 + 60*0.3 + 40*0.3 = 20 + 18 + 12 = 50
        assert quality.value == 50.0

    def test_create_empty_result(self, service, sample_project):
        result = service._create_empty_result(sample_project)

        assert result.project_id == sample_project.id
        assert result.clips == []
        assert result.quality_score == 0.0
        assert result.output_video_path == ""
