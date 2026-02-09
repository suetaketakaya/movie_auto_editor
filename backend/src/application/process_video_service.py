"""
Main video processing use case.
Decomposes the legacy app.py process_video_task (~450 lines) into a clean pipeline.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from backend.src.application.creative_director import CreativeDirector
from backend.src.application.dto.process_request import ProcessRequest
from backend.src.application.dto.process_result import ProcessResult
from backend.src.application.plugins.base_content_plugin import ContentPlugin
from backend.src.application.plugins.plugin_registry import PluginRegistry
from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.entities.project import Project, ProjectStatus
from backend.src.core.services.reward_calculator import RewardCalculator
from backend.src.core.value_objects.quality_score import QualityScore

logger = logging.getLogger(__name__)


class ProcessVideoService:
    """Orchestrates the full video processing pipeline."""

    def __init__(
        self,
        vision,       # VisionAnalysisPort
        editor,       # VideoEditingPort
        audio,        # AudioProcessingPort
        effects,      # VisualEffectsPort
        text_overlay,  # TextOverlayPort
        frame_extraction,  # FrameExtractionPort
        repository,   # ProjectRepositoryPort
        notifier,     # NotificationPort
        plugin_registry: Optional[PluginRegistry] = None,
    ):
        self._vision = vision
        self._editor = editor
        self._audio = audio
        self._effects = effects
        self._text_overlay = text_overlay
        self._frame_extraction = frame_extraction
        self._repository = repository
        self._notifier = notifier
        self._plugin_registry = plugin_registry or PluginRegistry.create_default()
        self._reward_calculator = RewardCalculator()

    async def execute(self, request: ProcessRequest) -> ProcessResult:
        """Execute the full processing pipeline."""
        project = Project(
            id=request.project_id,
            name=request.project_name,
            input_video_path=request.input_video_path,
            output_dir=request.output_dir,
            content_type=request.content_type,
            config=request.config,
        )
        project.start_processing()
        await self._repository.save(project)

        try:
            # 1. Select plugin
            plugin = self._plugin_registry.get_or_default(request.content_type)
            director_config = plugin.get_director_config()

            await self._notify(project, 0.05, "extracting_frames")

            # 2. Frame extraction
            frames_dir = Path(request.output_dir) / "frames"
            config = request.config or request.custom_config
            frame_paths = await self._frame_extraction.extract_frames(
                request.input_video_path,
                str(frames_dir),
                interval_seconds=config.get("interval_seconds", 5.0),
            )

            await self._notify(project, 0.15, "analyzing_frames")

            # 3. AI analysis
            analyses = await self._vision.analyze_frames_batch(
                frame_paths,
                concurrency=config.get("analysis_concurrency", 4),
            )

            await self._notify(project, 0.40, "selecting_clips")

            # 4. Creative direction (3-director system)
            director = CreativeDirector(config=director_config)
            decisions = director.direct(analyses, plugin=plugin)

            if not decisions.clips:
                logger.warning("No clips selected, creating fallback")
                return self._create_empty_result(project)

            await self._notify(project, 0.55, "editing_video")

            # 5. Video editing
            output_path = Path(request.output_dir) / "highlight.mp4"
            clip_dicts = [
                {"start": c.start, "end": c.end} for c in decisions.clips
            ]
            result_path = await self._editor.create_highlight(
                request.input_video_path, clip_dicts, str(output_path)
            )

            await self._notify(project, 0.70, "applying_effects")

            # 6. Post-processing (effects, audio, text)
            result_path = await self._apply_post_processing(
                result_path, decisions, request, plugin
            )

            await self._notify(project, 0.85, "evaluating_quality")

            # 7. Quality evaluation
            quality = self._evaluate_quality(decisions, analyses)

            # 8. Reward signal (for RL experiments)
            reward = self._reward_calculator.calculate_from_clips(
                decisions.clips,
                analyses,
                quality,
                target_duration=director_config.target_duration if director_config else 180.0,
            )

            await self._notify(project, 0.95, "finalizing")

            # 9. Complete
            result = ProcessResult(
                project_id=project.id,
                output_video_path=result_path,
                clips=[
                    {"start": c.start, "end": c.end, "type": c.clip_type, "reason": c.reason}
                    for c in decisions.clips
                ],
                quality_score=quality.value,
                reward_signal=reward.total,
                reward_components=reward.components,
                engagement_curve=decisions.engagement_curve,
                multi_events=decisions.multi_events,
                suggestions=decisions.suggestions,
                clip_count=len(decisions.clips),
                total_duration=sum(c.duration for c in decisions.clips),
            )

            project.complete(
                output_paths={"main": result_path},
                result=result.to_dict(),
            )
            await self._repository.save(project)
            await self._notifier.send_completion(project.id, result.to_dict())

            return result

        except Exception as e:
            logger.error("Processing failed for %s: %s", project.id, e)
            project.fail(str(e))
            await self._repository.save(project)
            await self._notifier.send_error(project.id, str(e))
            raise

    async def _apply_post_processing(
        self,
        video_path: str,
        decisions,
        request: ProcessRequest,
        plugin: Optional[ContentPlugin],
    ) -> str:
        """Apply effects, audio, and text overlays."""
        result_path = video_path
        config = request.config or request.custom_config

        # Color grading
        color_preset = config.get("color_preset", "cinematic")
        if color_preset and color_preset != "none":
            try:
                graded_path = str(Path(request.output_dir) / "graded.mp4")
                result_path = await self._effects.apply_color_grading(
                    result_path, graded_path, preset=color_preset
                )
            except Exception as e:
                logger.warning("Color grading failed: %s", e)

        # Audio normalization
        try:
            audio_path = str(Path(request.output_dir) / "audio_normalized.mp4")
            result_path = await self._audio.normalize_audio(result_path, audio_path)
        except Exception as e:
            logger.warning("Audio normalization failed: %s", e)

        # BGM
        bgm_path = config.get("bgm_path")
        if bgm_path:
            try:
                bgm_out = str(Path(request.output_dir) / "with_bgm.mp4")
                result_path = await self._audio.add_background_music(
                    result_path, bgm_path, bgm_out,
                    music_volume=config.get("audio_music_ratio", 0.3),
                )
            except Exception as e:
                logger.warning("BGM addition failed: %s", e)

        return result_path

    def _evaluate_quality(
        self, decisions, analyses: list[FrameAnalysis]
    ) -> QualityScore:
        """Evaluate output quality based on engagement metrics."""
        curve = decisions.engagement_curve
        avg_score = curve.get("avg_score", 0)
        pacing_score = curve.get("pacing_score", 0)
        variety = decisions.variety_analysis.get("variety_score", 0)

        composite = (avg_score * 0.4 + pacing_score * 0.3 + variety * 0.3)
        return QualityScore(value=min(100.0, composite))

    def _create_empty_result(self, project: Project) -> ProcessResult:
        project.complete(result={"clips": [], "quality_score": 0})
        return ProcessResult(
            project_id=project.id,
            output_video_path="",
            clips=[],
            quality_score=0.0,
            reward_signal=0.0,
        )

    async def _notify(
        self, project: Project, progress: float, stage: str
    ) -> None:
        project.update_progress(stage, int(progress * 100))
        await self._repository.save(project)
        await self._notifier.send_progress(project.id, stage, int(progress * 100), stage)
