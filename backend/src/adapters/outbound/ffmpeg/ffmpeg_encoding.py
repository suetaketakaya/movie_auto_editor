"""FFmpeg adapter for GPU/CPU video encoding."""
from __future__ import annotations

import asyncio
import logging
import subprocess

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import FFMPEG_PATH, run_ffmpeg

logger = logging.getLogger(__name__)

# quality -> CRF/CQ value mapping (shared across vendors)
_QUALITY_MAP: dict[str, str] = {
    "low": "30",
    "medium": "23",
    "high": "18",
    "ultra": "15",
}


class FFmpegEncoder:
    """Implements EncodingPort using FFmpeg with automatic GPU detection."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self._gpu: str = self._detect_gpu()

    # -- port interface ---------------------------------------------------------

    def encode_video(
        self,
        input_path: str,
        output_path: str,
        codec: str = "h264",
        quality: str = "high",
    ) -> str:
        logger.info("Encoding %s (codec=%s, quality=%s, gpu=%s)",
                     input_path, codec, quality, self._gpu)

        if self._gpu == "nvidia":
            return self._encode_nvidia(input_path, output_path, codec, quality)
        if self._gpu == "amd":
            return self._encode_amd(input_path, output_path, codec, quality)
        if self._gpu == "intel":
            return self._encode_intel(input_path, output_path, codec, quality)
        return self._encode_cpu(input_path, output_path, codec, quality)

    def detect_gpu(self) -> str:
        return self._gpu

    def get_supported_codecs(self) -> list[str]:
        codec_lists: dict[str, list[str]] = {
            "nvidia": ["h264", "h265", "av1"],
            "amd": ["h264", "h265"],
            "intel": ["h264", "h265"],
            "cpu": ["h264", "h265", "av1"],
        }
        return codec_lists.get(self._gpu, ["h264"])

    # -- GPU detection ----------------------------------------------------------

    def _detect_gpu(self) -> str:
        try:
            result = subprocess.run(
                [FFMPEG_PATH, "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5,
            )
            output = result.stdout

            if "h264_nvenc" in output:
                logger.info("NVIDIA NVENC detected")
                return "nvidia"
            if "h264_amf" in output:
                logger.info("AMD AMF detected")
                return "amd"
            if "h264_qsv" in output:
                logger.info("Intel QSV detected")
                return "intel"

            logger.info("No GPU encoder detected, using CPU")
            return "cpu"
        except Exception as exc:
            logger.warning("GPU detection failed: %s", exc)
            return "cpu"

    # -- vendor-specific encoding -----------------------------------------------

    def _encode_nvidia(
        self, input_path: str, output_path: str, codec: str, quality: str
    ) -> str:
        codec_map = {"h264": "h264_nvenc", "h265": "hevc_nvenc", "av1": "av1_nvenc"}
        cq = _QUALITY_MAP.get(quality, "18")

        run_ffmpeg([
            "-hwaccel", "cuda",
            "-i", str(input_path),
            "-c:v", codec_map.get(codec, "h264_nvenc"),
            "-preset", "p4",
            "-cq", cq,
            "-rc", "vbr",
            "-b:v", "0",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ])
        logger.info("NVIDIA NVENC encoding completed: %s", output_path)
        return str(output_path)

    def _encode_amd(
        self, input_path: str, output_path: str, codec: str, quality: str
    ) -> str:
        codec_map = {"h264": "h264_amf", "h265": "hevc_amf"}

        run_ffmpeg([
            "-i", str(input_path),
            "-c:v", codec_map.get(codec, "h264_amf"),
            "-quality", "quality",
            "-rc", "vbr_hq",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ])
        return str(output_path)

    def _encode_intel(
        self, input_path: str, output_path: str, codec: str, quality: str
    ) -> str:
        codec_map = {"h264": "h264_qsv", "h265": "hevc_qsv"}

        run_ffmpeg([
            "-hwaccel", "qsv",
            "-i", str(input_path),
            "-c:v", codec_map.get(codec, "h264_qsv"),
            "-preset", "slow",
            "-global_quality", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ])
        return str(output_path)

    def _encode_cpu(
        self, input_path: str, output_path: str, codec: str, quality: str
    ) -> str:
        codec_map = {"h264": "libx264", "h265": "libx265", "av1": "libaom-av1"}
        crf = _QUALITY_MAP.get(quality, "18")

        run_ffmpeg([
            "-i", str(input_path),
            "-c:v", codec_map.get(codec, "libx264"),
            "-preset", "slow",
            "-crf", crf,
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ])
        return str(output_path)

    # -- async convenience wrapper ----------------------------------------------

    async def encode_video_async(
        self, input_path: str, output_path: str,
        codec: str = "h264", quality: str = "high",
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.encode_video, input_path, output_path, codec, quality,
        )
