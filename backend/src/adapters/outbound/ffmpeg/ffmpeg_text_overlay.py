"""FFmpeg adapter for text overlay operations."""
from __future__ import annotations

import asyncio
import logging

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import (
    get_video_duration,
    run_ffmpeg,
)

logger = logging.getLogger(__name__)


class FFmpegTextOverlay:
    """Implements TextOverlayPort using FFmpeg drawtext / subtitle filters."""

    def __init__(self, config: dict) -> None:
        self.config = config

    # -- port interface ---------------------------------------------------------

    def add_kill_counter(
        self, input_path: str, output_path: str, kill_timestamps: list[float]
    ) -> str:
        logger.info("Adding kill counter: %d kills", len(kill_timestamps))

        drawtext_filters: list[str] = []
        for i, ts in enumerate(kill_timestamps, 1):
            end = ts + 3.0
            drawtext_filters.append(
                f"drawtext=text='{i} KILLS':"
                f"fontfile=/Windows/Fonts/impact.ttf:fontsize=48:"
                f"fontcolor=white:borderw=3:bordercolor=black:"
                f"x=(w-text_w)/2:y=50:"
                f"enable='between(t,{ts},{end})'"
            )

        vf = ",".join(drawtext_filters) if drawtext_filters else "null"
        run_ffmpeg([
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def add_text_popup(
        self,
        input_path: str,
        output_path: str,
        text: str,
        timestamp: float,
        duration: float = 2.0,
        position: str = "center",
    ) -> str:
        logger.info("Adding text popup '%s' at %.2fs", text, timestamp)

        y_positions = {
            "top": "100",
            "center": "(h-text_h)/2",
            "bottom": "h-text_h-100",
        }
        y_pos = y_positions.get(position, y_positions["center"])

        end = timestamp + duration
        fade_dur = 0.3

        vf = (
            f"drawtext=text='{text}':"
            f"fontfile=/Windows/Fonts/impact.ttf:fontsize=72:"
            f"fontcolor=yellow:borderw=5:bordercolor=black:"
            f"x=(w-text_w)/2:y={y_pos}:"
            f"alpha='if(lt(t,{timestamp + fade_dur}),(t-{timestamp})/{fade_dur},"
            f"if(gt(t,{end - fade_dur}),({end}-t)/{fade_dur},1))':"
            f"enable='between(t,{timestamp},{end})'"
        )

        run_ffmpeg([
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def add_subtitle(
        self, input_path: str, output_path: str, subtitle_file: str
    ) -> str:
        logger.info("Burning subtitles from %s", subtitle_file)
        # Escape Windows path for the subtitles filter
        escaped = subtitle_file.replace("\\", "/").replace(":", "\\:")

        run_ffmpeg([
            "-i", input_path,
            "-vf", f"subtitles={escaped}",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def add_custom_text(
        self,
        input_path: str,
        output_path: str,
        text: str,
        x: int = 50,
        y: int = 50,
        font_size: int = 36,
        color: str = "white",
    ) -> str:
        logger.info("Adding custom text '%s' at (%d, %d)", text, x, y)

        vf = (
            f"drawtext=text='{text}':"
            f"fontfile=/Windows/Fonts/arial.ttf:fontsize={font_size}:"
            f"fontcolor={color}:borderw=2:bordercolor=black:"
            f"x={x}:y={y}"
        )

        run_ffmpeg([
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def add_timestamp_overlay(self, input_path: str, output_path: str) -> str:
        logger.info("Adding timestamp overlay")

        vf = (
            "drawtext=text='%{pts\\:hms}':"
            "fontfile=/Windows/Fonts/consola.ttf:fontsize=24:"
            "fontcolor=white:borderw=2:bordercolor=black:"
            "x=w-text_w-20:y=20"
        )

        run_ffmpeg([
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def add_progress_bar(
        self, input_path: str, output_path: str, total_duration: float
    ) -> str:
        logger.info("Adding progress bar")

        vf = (
            "drawbox=x=50:y=h-80:w=w-100:h=10:color=gray@0.5:t=fill,"
            f"drawbox=x=50:y=h-80:w='(w-100)*t/{total_duration}':h=10:color=red:t=fill"
        )

        run_ffmpeg([
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    # -- async convenience wrappers ---------------------------------------------

    async def add_text_popup_async(
        self, input_path: str, output_path: str, text: str,
        timestamp: float, duration: float = 2.0, position: str = "center",
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.add_text_popup, input_path, output_path,
            text, timestamp, duration, position,
        )

    async def add_subtitle_async(
        self, input_path: str, output_path: str, subtitle_file: str,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.add_subtitle, input_path, output_path, subtitle_file,
        )

    async def add_custom_text_async(
        self, input_path: str, output_path: str, text: str,
        x: int = 50, y: int = 50, font_size: int = 36, color: str = "white",
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.add_custom_text, input_path, output_path,
            text, x, y, font_size, color,
        )
