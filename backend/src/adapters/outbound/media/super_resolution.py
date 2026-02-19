"""Super-resolution adapter (RealESRGAN + FFmpeg fallback).

Wraps the legacy ``src.super_resolution.SuperResolution`` logic and
exposes it through a clean adapter interface for the hexagonal
architecture.  When the ``realesrgan-ncnn-vulkan`` binary is available
on the system it is used for AI upscaling; otherwise the adapter falls
back to high-quality Lanczos scaling via FFmpeg.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import (
    get_video_resolution,
    run_ffmpeg,
)

logger = logging.getLogger(__name__)

_SUPPORTED_SCALES = (2, 4)


class SuperResolutionAdapter:
    """AI / Lanczos video upscaling adapter.

    Configuration is read from ``config["super_resolution"]`` with the
    following optional keys:

    * ``enable`` (bool, default ``True``) -- set to ``False`` to skip
      upscaling entirely.
    * ``enhance_faces`` (bool, default ``False``) -- placeholder for
      future GFPGAN integration.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._sr_cfg: dict[str, Any] = config.get("super_resolution", {})
        self._enabled: bool = self._sr_cfg.get("enable", True)

    # -- Public async API ------------------------------------------------------

    async def upscale_video(
        self,
        input_path: str,
        output_path: str,
        scale: int = 2,
        model: str = "realesrgan-x4plus",
    ) -> str:
        """Upscale a video by the given *scale* factor (2 or 4).

        Returns the *output_path* on success, or *input_path* unchanged
        when upscaling is disabled or fails gracefully.
        """
        if not self._enabled:
            logger.info("Super resolution is disabled; returning original")
            return input_path

        if scale not in _SUPPORTED_SCALES:
            raise ValueError(
                f"Unsupported scale factor {scale}; choose from {_SUPPORTED_SCALES}"
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._upscale_sync, input_path, output_path, scale, model
        )

    # -- Private sync implementation -------------------------------------------

    def _upscale_sync(
        self,
        input_path: str,
        output_path: str,
        scale: int,
        model: str,
    ) -> str:
        logger.info(
            "Starting super resolution: %s -> %s (scale=%dx, model=%s)",
            input_path, output_path, scale, model,
        )

        try:
            if self._is_realesrgan_available():
                return self._upscale_realesrgan(input_path, output_path, scale, model)
            else:
                logger.warning(
                    "Real-ESRGAN not available; falling back to FFmpeg Lanczos upscaling"
                )
                return self._upscale_ffmpeg(input_path, output_path, scale)
        except Exception:
            logger.exception("Super resolution failed; returning original path")
            return input_path

    # -- Real-ESRGAN path ------------------------------------------------------

    @staticmethod
    def _is_realesrgan_available() -> bool:
        try:
            result = subprocess.run(
                ["realesrgan-ncnn-vulkan", "-h"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _upscale_realesrgan(
        self,
        input_path: str,
        output_path: str,
        scale: int,
        model: str,
    ) -> str:
        logger.info("Using Real-ESRGAN for super resolution")

        temp_frames = Path(output_path).parent / "_sr_frames"
        temp_upscaled = Path(output_path).parent / "_sr_upscaled"
        temp_frames.mkdir(parents=True, exist_ok=True)
        temp_upscaled.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Extract frames
            logger.info("Extracting frames for upscaling")
            run_ffmpeg([
                "-i", input_path,
                "-qscale:v", "1",
                str(temp_frames / "frame_%06d.png"),
            ])

            # 2. Upscale each frame with Real-ESRGAN
            logger.info("Upscaling frames with Real-ESRGAN (model=%s)", model)
            subprocess.run(
                [
                    "realesrgan-ncnn-vulkan",
                    "-i", str(temp_frames),
                    "-o", str(temp_upscaled),
                    "-n", model,
                    "-s", str(scale),
                    "-f", "png",
                ],
                check=True,
                capture_output=True,
            )

            # 3. Reassemble into video (preserving original audio)
            logger.info("Reassembling upscaled frames into video")
            run_ffmpeg([
                "-framerate", "60",
                "-i", str(temp_upscaled / "frame_%06d.png"),
                "-i", input_path,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18",
                "-c:a", "copy",
                str(output_path),
            ])

            logger.info("Real-ESRGAN upscaling completed: %s", output_path)
            return str(output_path)
        finally:
            if temp_frames.exists():
                shutil.rmtree(temp_frames, ignore_errors=True)
            if temp_upscaled.exists():
                shutil.rmtree(temp_upscaled, ignore_errors=True)

    # -- FFmpeg Lanczos fallback -----------------------------------------------

    def _upscale_ffmpeg(
        self,
        input_path: str,
        output_path: str,
        scale: int,
    ) -> str:
        width, height = get_video_resolution(input_path)
        new_w = width * scale
        new_h = height * scale

        logger.info(
            "FFmpeg Lanczos upscaling %dx%d -> %dx%d",
            width, height, new_w, new_h,
        )

        run_ffmpeg([
            "-i", input_path,
            "-vf", f"scale={new_w}:{new_h}:flags=lanczos",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path),
        ])

        logger.info("FFmpeg Lanczos upscaling completed: %s", output_path)
        return str(output_path)
