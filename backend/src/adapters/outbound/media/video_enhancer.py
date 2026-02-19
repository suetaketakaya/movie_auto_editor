"""FFmpeg-based video enhancement adapter.

Wraps the legacy ``src.video_enhancer.VideoEnhancer`` logic (denoise,
sharpen, LUT colour grading, stabilisation, auto-correction, full
pipeline) and exposes it through a clean adapter interface for the
hexagonal architecture.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import run_ffmpeg

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Preset look-up tables
# --------------------------------------------------------------------------- #

_DENOISE_PRESETS: dict[str, str] = {
    "light": "hqdn3d=1.5:1.5:6:6",
    "medium": "hqdn3d=2.0:2.0:8:8,nlmeans=s=1.5:p=7:r=15",
    "strong": "hqdn3d=3.0:3.0:10:10,nlmeans=s=3.0:p=7:r=15",
}

_LUT_PRESETS: dict[str, str] = {
    "cinematic": "eq=contrast=1.2:brightness=0.05:saturation=0.9,curves=vintage",
    "teal_orange": "curves=r='0/0 0.5/0.4 1/1':g='0/0 0.5/0.5 1/1':b='0/0.1 0.5/0.6 1/1'",
    "vintage": "curves=vintage,eq=saturation=0.8:contrast=1.15",
    "warm": "eq=contrast=1.05:saturation=1.1,colortemperature=7000",
    "cool": "eq=contrast=1.05:saturation=1.1,colortemperature=3000",
    "vibrant": "eq=contrast=1.15:saturation=1.4:gamma=1.05",
    "moody": "curves=preset=darker:vintage,eq=saturation=0.7",
    "bleach_bypass": "eq=contrast=1.3:saturation=0.6,curves=strong_contrast",
    "desaturated": "eq=saturation=0.4",
}

# Common encoding flags appended to every enhancement command.
_ENC_ARGS: list[str] = [
    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-c:a", "copy",
]


class VideoEnhancerAdapter:
    """Video quality enhancement adapter backed by FFmpeg filters.

    Provides individual effects (denoise, sharpen, LUT, stabilise) as well as
    a combined ``enhance_video`` pipeline that chains multiple effects in a
    single FFmpeg invocation.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._enh_cfg: dict[str, Any] = config.get("video_enhancer", {})

    # -- High-level async API --------------------------------------------------

    async def enhance_video(
        self,
        input_path: str,
        output_path: str,
        *,
        denoise: bool = True,
        sharpen: bool = True,
        color_grade: bool = True,
        stabilize: bool = False,
        grain: bool = False,
    ) -> str:
        """Run the full enhancement pipeline.

        When *stabilize* is ``True`` the pipeline performs a two-pass
        stabilisation **before** the other filters, writing an intermediate
        file that is then fed through the remaining filter chain.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._enhance_video_sync,
            input_path,
            output_path,
            denoise,
            sharpen,
            color_grade,
            stabilize,
            grain,
        )

    async def denoise(
        self,
        input_path: str,
        output_path: str,
        strength: str = "medium",
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._denoise_sync, input_path, output_path, strength
        )

    async def sharpen(
        self,
        input_path: str,
        output_path: str,
        amount: float = 1.0,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sharpen_sync, input_path, output_path, amount
        )

    async def apply_lut(
        self,
        input_path: str,
        output_path: str,
        preset: str = "cinematic",
        lut_file: Optional[str] = None,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._apply_lut_sync, input_path, output_path, preset, lut_file
        )

    async def stabilize(
        self,
        input_path: str,
        output_path: str,
        smoothing: int = 10,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._stabilize_sync, input_path, output_path, smoothing
        )

    # -- Private sync implementations -----------------------------------------

    def _denoise_sync(self, inp: str, out: str, strength: str) -> str:
        logger.info("Applying denoise (strength=%s): %s", strength, inp)
        vf = _DENOISE_PRESETS.get(strength, _DENOISE_PRESETS["medium"])
        run_ffmpeg(["-i", inp, "-vf", vf, *_ENC_ARGS, str(out)])
        logger.info("Denoise completed: %s", out)
        return str(out)

    def _sharpen_sync(self, inp: str, out: str, amount: float) -> str:
        logger.info("Applying sharpness (amount=%.2f): %s", amount, inp)
        vf = f"unsharp=5:5:{amount}:5:5:0.0"
        run_ffmpeg(["-i", inp, "-vf", vf, *_ENC_ARGS, str(out)])
        logger.info("Sharpness enhancement completed: %s", out)
        return str(out)

    def _apply_lut_sync(
        self,
        inp: str,
        out: str,
        preset: str,
        lut_file: Optional[str],
    ) -> str:
        logger.info("Applying LUT grading (preset=%s): %s", preset, inp)

        if lut_file and Path(lut_file).exists():
            vf = f"lut3d={lut_file}"
        else:
            vf = _LUT_PRESETS.get(preset, _LUT_PRESETS["cinematic"])

        run_ffmpeg(["-i", inp, "-vf", vf, *_ENC_ARGS, str(out)])
        logger.info("LUT grading completed (%s): %s", preset, out)
        return str(out)

    def _stabilize_sync(self, inp: str, out: str, smoothing: int) -> str:
        logger.info("Stabilising video (smoothing=%d): %s", smoothing, inp)

        transforms_file = Path(out).with_suffix(".trf")

        try:
            # Pass 1 -- motion detection
            run_ffmpeg([
                "-i", inp,
                "-vf", f"vidstabdetect=shakiness=10:accuracy=15:result={transforms_file}",
                "-f", "null", "-",
            ])

            # Pass 2 -- apply stabilisation transform
            run_ffmpeg([
                "-i", inp,
                "-vf", (
                    f"vidstabtransform=input={transforms_file}"
                    f":smoothing={smoothing}:zoom=1:optalgo=gauss"
                ),
                *_ENC_ARGS,
                str(out),
            ])

            logger.info("Video stabilisation completed: %s", out)
            return str(out)
        finally:
            if transforms_file.exists():
                transforms_file.unlink()

    def _enhance_video_sync(
        self,
        inp: str,
        out: str,
        do_denoise: bool,
        do_sharpen: bool,
        do_color_grade: bool,
        do_stabilize: bool,
        do_grain: bool,
    ) -> str:
        logger.info("Running full enhancement pipeline on: %s", inp)

        current_input = inp
        cfg = self._enh_cfg

        # Stabilisation must be performed as a separate two-pass step.
        if do_stabilize:
            stab_out = str(Path(out).with_suffix(".stab.mp4"))
            smoothing = cfg.get("stabilize", {}).get("smoothing", 10)
            self._stabilize_sync(current_input, stab_out, smoothing)
            current_input = stab_out

        # Build a single-pass filter chain for remaining effects.
        filters: list[str] = []

        if do_denoise:
            strength = cfg.get("denoise", {}).get("strength", "medium")
            # Use the simpler hqdn3d only for the combined chain to avoid
            # excessive processing time.
            denoise_chain = {
                "light": "hqdn3d=1.5:1.5:6:6",
                "medium": "hqdn3d=2.0:2.0:8:8",
                "strong": "hqdn3d=3.0:3.0:10:10",
            }
            filters.append(denoise_chain.get(strength, "hqdn3d=2.0:2.0:8:8"))

        if do_sharpen:
            amount = cfg.get("sharpen", {}).get("amount", 1.0)
            filters.append(f"unsharp=5:5:{amount}:5:5:0.0")

        if do_color_grade:
            preset = cfg.get("lut", {}).get("preset", "cinematic")
            filters.append(_LUT_PRESETS.get(preset, _LUT_PRESETS["cinematic"]))

        if do_grain:
            strength = cfg.get("grain", {}).get("strength", 0.3)
            filters.append(f"noise=alls={int(strength * 20)}:allf=t+u")

        vf = ",".join(filters) if filters else "copy"

        run_ffmpeg(["-i", current_input, "-vf", vf, *_ENC_ARGS, str(out)])

        # Clean up intermediate stabilisation file if it was created.
        if do_stabilize and current_input != inp:
            try:
                Path(current_input).unlink()
            except OSError:
                pass

        logger.info("Full enhancement pipeline completed: %s", out)
        return str(out)
