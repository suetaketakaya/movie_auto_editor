"""
Main video processing use case.
Decomposes the legacy app.py process_video_task (~450 lines) into a clean pipeline.
"""
from __future__ import annotations

import asyncio
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

# Quality gate threshold (0-100)
QUALITY_GATE_THRESHOLD = 30.0


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

        warnings: list[str] = []

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
                interval_seconds=config.get("interval_seconds", 2.0),
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
                result_path, decisions, request, plugin, warnings
            )

            await self._notify(project, 0.85, "evaluating_quality")

            # 7. Quality evaluation
            quality = self._evaluate_quality(decisions, analyses)

            # 8. Quality gate check
            if quality.value < QUALITY_GATE_THRESHOLD:
                warning_msg = (
                    f"Low quality score ({quality.value:.1f}/{QUALITY_GATE_THRESHOLD}). "
                    "The source video may lack highlight-worthy content."
                )
                warnings.append(warning_msg)
                logger.warning("Quality gate warning for %s: %s", project.id, warning_msg)
                await self._notify(project, 0.87, "quality_warning")

            # 9. Reward signal (for RL experiments)
            reward = self._reward_calculator.calculate_from_clips(
                decisions.clips,
                analyses,
                quality,
                target_duration=director_config.target_duration if director_config else 180.0,
            )

            # 10. Thumbnail generation
            thumbnail_path = await self._generate_thumbnail(
                result_path, decisions.clips, request.output_dir
            )

            await self._notify(project, 0.95, "finalizing")

            # 11. Complete
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
                warnings=warnings,
                thumbnail_path=thumbnail_path or "",
            )

            project.complete(
                output_paths={"main": result_path, "thumbnail": thumbnail_path or ""},
                result=result.to_dict(),
            )
            await self._repository.save(project)
            await self._notify_completion(project.id, result.to_dict())

            return result

        except Exception as e:
            logger.error("Processing failed for %s: %s", project.id, e)
            project.fail(str(e))
            await self._repository.save(project)
            await self._notify_error(project.id, str(e))
            raise

    async def _apply_post_processing(
        self,
        video_path: str,
        decisions,
        request: ProcessRequest,
        plugin: Optional[ContentPlugin],
        warnings: list[str],
    ) -> str:
        """Apply effects, audio, and text overlays. Collect warnings for failures."""
        result_path = video_path
        config = request.config or request.custom_config

        out = Path(request.output_dir)

        # 1. Color grading
        color_preset = config.get("color_preset", "cinematic")
        if color_preset and color_preset != "none":
            try:
                graded_path = str(out / "graded.mp4")
                loop = asyncio.get_event_loop()
                result_path = await loop.run_in_executor(
                    None, self._effects.apply_color_grading,
                    result_path, graded_path, color_preset,
                )
            except Exception as e:
                logger.warning("Color grading failed: %s", e)
                warnings.append(f"Color grading skipped: {e}")

        # 2. Vignette
        try:
            vignette_path = str(out / "vignette.mp4")
            loop = asyncio.get_event_loop()
            result_path = await loop.run_in_executor(
                None, self._effects.apply_vignette,
                result_path, vignette_path, 0.3,
            )
        except Exception as e:
            logger.warning("Vignette failed: %s", e)
            warnings.append(f"Vignette skipped: {e}")

        # 3. Text overlays (kill counter + multi-kill popups)
        kill_timestamps = self._extract_kill_timestamps(decisions)
        if kill_timestamps:
            try:
                counter_path = str(out / "kill_counter.mp4")
                result_path = await self._apply_kill_counter(
                    result_path, counter_path, kill_timestamps
                )
            except Exception as e:
                logger.warning("Kill counter overlay failed: %s", e)
                warnings.append(f"Kill counter skipped: {e}")

        multi_events = getattr(decisions, "multi_events", []) or []
        if multi_events:
            try:
                result_path = await self._apply_multi_kill_popups(
                    result_path, out, multi_events, warnings
                )
            except Exception as e:
                logger.warning("Multi-kill popup failed: %s", e)
                warnings.append(f"Multi-kill popups skipped: {e}")

        # 4. Game audio enhancement
        try:
            game_audio_path = str(out / "game_audio.mp4")
            result_path = await self._apply_game_audio(
                result_path, game_audio_path
            )
        except Exception as e:
            logger.warning("Game audio enhancement failed: %s", e)
            warnings.append(f"Game audio enhancement skipped: {e}")

        # 5. Audio normalization
        try:
            audio_path = str(out / "audio_normalized.mp4")
            loop = asyncio.get_event_loop()
            result_path = await loop.run_in_executor(
                None, self._audio.normalize_audio, result_path, audio_path,
            )
        except Exception as e:
            logger.warning("Audio normalization failed: %s", e)
            warnings.append(f"Audio normalization skipped: {e}")

        # 6. BGM
        bgm_path = config.get("bgm_path")
        if bgm_path:
            try:
                bgm_out = str(out / "with_bgm.mp4")
                loop = asyncio.get_event_loop()
                result_path = await loop.run_in_executor(
                    None, self._audio.add_background_music,
                    result_path, bgm_path, bgm_out,
                    0.7, config.get("audio_music_ratio", 0.3),
                )
            except Exception as e:
                logger.warning("BGM addition failed: %s", e)
                warnings.append(f"Background music skipped: {e}")

        # 7. Audio fade in/out
        try:
            fade_path = str(out / "faded.mp4")
            result_path = await self._apply_audio_fade(result_path, fade_path)
        except Exception as e:
            logger.warning("Audio fade failed: %s", e)
            warnings.append(f"Audio fade skipped: {e}")

        # 8. GPU re-encode (final quality pass)
        try:
            encoded_path = str(out / "final_encoded.mp4")
            result_path = await self._apply_gpu_reencode(
                result_path, encoded_path
            )
        except Exception as e:
            logger.warning("GPU re-encode failed: %s", e)
            warnings.append(f"GPU re-encode skipped: {e}")

        return result_path

    async def _generate_thumbnail(
        self, video_path: str, clips: list, output_dir: str
    ) -> Optional[str]:
        """Generate thumbnail from the highest-scoring clip frame."""
        if not clips:
            return None
        try:
            # Find the best clip's midpoint timestamp
            best_clip = max(clips, key=lambda c: c.score.value if hasattr(c, 'score') else 0)
            timestamp = (best_clip.start + best_clip.end) / 2

            thumbnail_path = str(Path(output_dir) / "thumbnail.jpg")

            from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import run_ffmpeg
            run_ffmpeg([
                "-ss", str(timestamp),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                thumbnail_path,
            ])

            if Path(thumbnail_path).exists():
                logger.info("Thumbnail generated at %.2fs: %s", timestamp, thumbnail_path)
                return thumbnail_path
        except Exception as e:
            logger.warning("Thumbnail generation failed: %s", e)
        return None

    def _extract_kill_timestamps(self, decisions) -> list[float]:
        """Extract kill timestamps from clip decisions for overlay."""
        timestamps: list[float] = []
        for clip in (decisions.clips or []):
            if hasattr(clip, "clip_type") and clip.clip_type in ("kill", "highlight", "action"):
                timestamps.append(clip.start)
        return timestamps

    async def _apply_kill_counter(
        self, video_path: str, output_path: str, kill_timestamps: list[float]
    ) -> str:
        """Apply kill counter overlay using the text overlay adapter."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._text_overlay.add_kill_counter,
            video_path, output_path, kill_timestamps,
        )

    async def _apply_multi_kill_popups(
        self,
        video_path: str,
        out_dir: Path,
        multi_events: list[dict],
        warnings: list[str],
    ) -> str:
        """Apply MULTI KILL text popups for each multi-kill event."""
        _MULTI_LABELS = {
            2: "DOUBLE KILL",
            3: "TRIPLE KILL",
            4: "QUADRA KILL",
            5: "ACE",
        }
        result_path = video_path
        loop = asyncio.get_event_loop()
        for i, event in enumerate(multi_events):
            count = event.get("kill_count", event.get("count", 2))
            ts = event.get("timestamp", event.get("start", 0))
            label = _MULTI_LABELS.get(count, f"{count}x MULTI KILL")
            popup_path = str(out_dir / f"popup_{i}.mp4")
            try:
                result_path = await loop.run_in_executor(
                    None, self._text_overlay.add_text_popup,
                    result_path, popup_path, label, ts, 2.0, "center",
                )
            except Exception as e:
                logger.warning("Multi-kill popup %d failed: %s", i, e)
                warnings.append(f"Multi-kill popup '{label}' skipped: {e}")
        return result_path

    async def _apply_game_audio(self, video_path: str, output_path: str) -> str:
        """Apply game audio enhancement preset."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._audio.enhance_game_audio, video_path, output_path,
        )

    async def _apply_audio_fade(self, video_path: str, output_path: str) -> str:
        """Apply audio fade in/out."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._audio.fade_in_out, video_path, output_path, 1.0, 1.0,
        )

    async def _apply_gpu_reencode(self, video_path: str, output_path: str) -> str:
        """Final GPU re-encode pass for consistent quality."""
        encoder = self._get_encoder()
        if encoder is None:
            return video_path
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, encoder.encode_video, video_path, output_path, "h264", "high",
        )

    def _get_encoder(self):
        """Lazy-get the encoder adapter if available."""
        if not hasattr(self, "_encoder"):
            try:
                from backend.src.adapters.outbound.ffmpeg.ffmpeg_encoding import FFmpegEncoder
                self._encoder = FFmpegEncoder(config={})
            except Exception:
                self._encoder = None
        return self._encoder

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
        """Send progress notification. Failures are logged but don't halt the pipeline."""
        try:
            project.update_progress(stage, int(progress * 100))
            await self._repository.save(project)
            await self._notifier.send_progress(project.id, stage, int(progress * 100), stage)
        except Exception as e:
            logger.warning("Notification failed for %s at stage %s: %s", project.id, stage, e)

    async def _notify_completion(self, project_id: str, result: dict) -> None:
        """Send completion notification. Failures don't halt the pipeline."""
        try:
            await self._notifier.send_completion(project_id, result)
        except Exception as e:
            logger.warning("Completion notification failed for %s: %s", project_id, e)

    async def _notify_error(self, project_id: str, error: str) -> None:
        """Send error notification. Failures don't halt the pipeline."""
        try:
            await self._notifier.send_error(project_id, error)
        except Exception as e:
            logger.warning("Error notification failed for %s: %s", project_id, e)
