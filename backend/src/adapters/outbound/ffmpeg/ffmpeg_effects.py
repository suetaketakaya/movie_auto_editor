"""FFmpeg adapter for visual effects operations."""
from __future__ import annotations

import asyncio
import logging

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import run_ffmpeg

logger = logging.getLogger(__name__)

# Colour-grading presets: filter_name -> FFmpeg video-filter string
_COLOR_PRESETS: dict[str, str] = {
    "cinematic": "eq=contrast=1.2:brightness=0.05:saturation=0.9,curves=vintage",
    "vibrant": "eq=contrast=1.1:saturation=1.3",
    "warm": "eq=contrast=1.05:saturation=1.1,colortemperature=7000",
    "cool": "eq=contrast=1.05:saturation=1.1,colortemperature=3000",
    "desaturated": "eq=saturation=0.7:contrast=1.15",
}


class FFmpegVisualEffects:
    """Implements VisualEffectsPort using FFmpeg CLI."""

    def __init__(self, config: dict) -> None:
        self.config = config

    # -- port interface ---------------------------------------------------------

    def apply_transition(
        self,
        clip1: str,
        clip2: str,
        output_path: str,
        transition_type: str = "fade",
        duration: float = 0.5,
    ) -> str:
        logger.info("Applying %s transition between clips", transition_type)
        run_ffmpeg([
            "-i", clip1,
            "-i", clip2,
            "-filter_complex",
            (
                f"[0:v][1:v]xfade=transition={transition_type}"
                f":duration={duration}:offset=0[vout];"
                f"[0:a][1:a]acrossfade=d={duration}[aout]"
            ),
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-c:a", "aac",
            str(output_path),
        ])
        return str(output_path)

    def apply_slow_motion(
        self,
        input_path: str,
        output_path: str,
        start_time: float = 0.0,
        end_time: float = 0.0,
        speed: float = 0.5,
    ) -> str:
        logger.info(
            "Applying slow motion %.2fs-%.2fs at %.2fx", start_time, end_time, speed
        )
        pts_factor = 1.0 / speed
        run_ffmpeg([
            "-i", input_path,
            "-filter_complex",
            f"[0:v]setpts={pts_factor}*PTS[v];[0:a]atempo={speed}[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-c:a", "aac",
            str(output_path),
        ])
        return str(output_path)

    def apply_color_grading(
        self, input_path: str, output_path: str, preset: str = "cinematic"
    ) -> str:
        logger.info("Applying color grading: %s", preset)
        filter_str = _COLOR_PRESETS.get(preset, _COLOR_PRESETS["cinematic"])
        run_ffmpeg([
            "-i", input_path,
            "-vf", filter_str,
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def apply_vignette(
        self, input_path: str, output_path: str, intensity: float = 0.3
    ) -> str:
        logger.info("Applying vignette (intensity=%.2f)", intensity)
        run_ffmpeg([
            "-i", input_path,
            "-vf", f"vignette=PI/4*{intensity}",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def apply_zoom(
        self,
        input_path: str,
        output_path: str,
        zoom_factor: float = 1.5,
        duration: float = 2.0,
    ) -> str:
        logger.info("Applying zoom (factor=%.2f)", zoom_factor)
        frames = int(duration * 30)
        run_ffmpeg([
            "-i", input_path,
            "-filter_complex",
            (
                f"[0:v]zoompan=z='min(zoom+0.0015,{zoom_factor})':"
                f"d={frames}:s=1920x1080[v]"
            ),
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def apply_shake(
        self, input_path: str, output_path: str, intensity: int = 5
    ) -> str:
        logger.info("Applying shake effect (intensity=%d)", intensity)
        d = intensity * 2
        run_ffmpeg([
            "-i", input_path,
            "-vf",
            (
                f"crop=in_w-{d}:in_h-{d}:"
                f"x={intensity}*sin(2*PI*t):y={intensity}*cos(2*PI*t)"
            ),
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def apply_chromatic_aberration(
        self, input_path: str, output_path: str
    ) -> str:
        logger.info("Applying chromatic aberration effect")
        run_ffmpeg([
            "-i", input_path,
            "-filter_complex",
            (
                "[0:v]split=3[r][g][b];"
                "[r]lutrgb=r=val:g=0:b=0[red];"
                "[g]lutrgb=r=0:g=val:b=0,pad=iw+4:ih:2:0[green];"
                "[b]lutrgb=r=0:g=0:b=val,pad=iw+4:ih:2:0[blue];"
                "[red][green]blend=all_mode=addition[rg];"
                "[rg][blue]blend=all_mode=addition[v]"
            ),
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    # -- async convenience wrappers ---------------------------------------------

    async def apply_transition_async(
        self, clip1: str, clip2: str, output_path: str,
        transition_type: str = "fade", duration: float = 0.5,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.apply_transition, clip1, clip2, output_path,
            transition_type, duration,
        )

    async def apply_slow_motion_async(
        self, input_path: str, output_path: str,
        start_time: float = 0.0, end_time: float = 0.0, speed: float = 0.5,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.apply_slow_motion, input_path, output_path,
            start_time, end_time, speed,
        )

    async def apply_color_grading_async(
        self, input_path: str, output_path: str, preset: str = "cinematic",
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.apply_color_grading, input_path, output_path, preset,
        )

    async def apply_zoom_async(
        self, input_path: str, output_path: str,
        zoom_factor: float = 1.5, duration: float = 2.0,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.apply_zoom, input_path, output_path,
            zoom_factor, duration,
        )
