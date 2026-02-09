"""FFmpeg adapter for video editing operations."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import (
    FFMPEG_PATH,
    get_video_metadata,
    get_video_resolution,
    run_ffmpeg,
)

if TYPE_CHECKING:
    from backend.src.core.entities.clip import Clip

logger = logging.getLogger(__name__)


class FFmpegVideoEditor:
    """Implements VideoEditingPort using FFmpeg CLI."""

    def __init__(self, config: dict) -> None:
        export = config.get("export", {})
        self.codec: str = export.get("codec", "libx264")
        self.crf: int = export.get("crf", 23)
        self.preset: str = export.get("preset", "medium")
        self.maintain_fps: bool = export.get("maintain_fps", False)

    # -- public (port) interface ------------------------------------------------

    async def create_highlight(
        self, input_video: str, clips: list[Clip], output_path: str
    ) -> str:
        if not clips:
            logger.warning("No clips provided; copying source video as-is")
            return await self.copy_video(input_video, output_path)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._create_highlight_sync, input_video, clips, output_path
        )

    async def concatenate_clips(
        self, clip_paths: list[str], output_path: str
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._concatenate_clips, clip_paths, output_path
        )

    async def copy_video(self, input_path: str, output_path: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._copy_video_sync, input_path, output_path
        )

    def get_video_metadata(self, video_path: str) -> dict:
        return get_video_metadata(video_path)

    def create_vertical_crop(
        self, input_video: str, output_path: str, position: str = "center"
    ) -> str:
        width, height = get_video_resolution(input_video)
        target_width = int(height * 9 / 16)
        x_offset = (width - target_width) // 2

        run_ffmpeg([
            "-i", input_video,
            "-vf", f"crop={target_width}:{height}:{x_offset}:0",
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", self.preset,
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    # -- private helpers --------------------------------------------------------

    def _create_highlight_sync(
        self, input_video: str, clips: list[Clip], output_path: str
    ) -> str:
        logger.info("Creating highlight video with %d clips", len(clips))
        temp_clips: list[str] = []

        try:
            for i, clip in enumerate(clips):
                start = clip.start
                duration = clip.end - clip.start
                temp_path = Path(output_path).parent / f"temp_clip_{i:03d}.mp4"

                logger.info(
                    "Extracting clip %d/%d: %.2fs - %.2fs",
                    i + 1, len(clips), start, clip.end,
                )
                cmd = self._build_extract_command(input_video, start, duration, temp_path)
                run_ffmpeg(cmd)
                temp_clips.append(str(temp_path))

            if len(temp_clips) == 1:
                Path(temp_clips[0]).rename(output_path)
            else:
                self._concatenate_clips(temp_clips, output_path)

            logger.info("Highlight video created: %s", output_path)
            return str(output_path)
        finally:
            for path in temp_clips:
                try:
                    p = Path(path)
                    if p.exists() and str(p) != str(output_path):
                        p.unlink()
                except OSError as exc:
                    logger.warning("Failed to delete temp file %s: %s", path, exc)

    def _build_extract_command(
        self, input_video: str, start: float, duration: float, output: Path
    ) -> list[str]:
        cmd = [
            "-ss", str(start),
            "-i", input_video,
            "-t", str(duration),
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", self.preset,
            "-c:a", "aac",
            "-b:a", "192k",
        ]
        if self.maintain_fps:
            cmd.extend(["-r", "60"])
        cmd.append(str(output))
        return cmd

    def _concatenate_clips(self, clip_paths: list[str], output_path: str) -> str:
        logger.info("Concatenating %d clips", len(clip_paths))
        concat_file = Path(output_path).parent / "concat_list.txt"

        with open(concat_file, "w", encoding="utf-8") as fh:
            for clip_path in clip_paths:
                abs_path = Path(clip_path).absolute()
                fh.write(f"file '{abs_path}'\n")

        try:
            run_ffmpeg([
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path),
            ])
        finally:
            if concat_file.exists():
                concat_file.unlink()

        return str(output_path)

    def _copy_video_sync(self, input_path: str, output_path: str) -> str:
        run_ffmpeg(["-i", input_path, "-c", "copy", str(output_path)])
        return str(output_path)
