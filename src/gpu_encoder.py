"""
GPU Accelerated Encoding Module
GPUアクセラレーション対応エンコーダー (NVENC, H.265/HEVC, AV1)
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
FFMPEG_PATH = "ffmpeg"


class GPUEncoder:
    """GPUエンコーダークラス"""

    def __init__(self, config: dict):
        self.config = config
        self.gpu_config = config.get("gpu_encoder", {})
        self.gpu_available = self._detect_gpu()

    def _detect_gpu(self) -> str:
        """利用可能なGPUエンコーダーを検出"""
        try:
            # NVIDIAチェック
            result = subprocess.run(
                [FFMPEG_PATH, "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout

            if "h264_nvenc" in output:
                logger.info("NVIDIA NVENC detected")
                return "nvidia"
            elif "h264_amf" in output:
                logger.info("AMD AMF detected")
                return "amd"
            elif "h264_qsv" in output:
                logger.info("Intel QSV detected")
                return "intel"
            else:
                logger.info("No GPU encoder detected, using CPU")
                return "cpu"
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
            return "cpu"

    def encode_video(self, input_path: str, output_path: str,
                    codec: str = "h264", quality: str = "high",
                    preset: str = "p4") -> str:
        """
        GPU加速エンコード

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス
            codec: コーデック (h264, h265, av1)
            quality: 品質 (low, medium, high, ultra)
            preset: プリセット (p1-p7, fast, medium, slow)

        Returns:
            出力ファイルパス
        """
        logger.info(f"GPU encoding: {codec} with {quality} quality")

        if self.gpu_available == "nvidia":
            return self._encode_nvidia(input_path, output_path, codec, quality, preset)
        elif self.gpu_available == "amd":
            return self._encode_amd(input_path, output_path, codec, quality)
        elif self.gpu_available == "intel":
            return self._encode_intel(input_path, output_path, codec, quality)
        else:
            return self._encode_cpu(input_path, output_path, codec, quality)

    def _encode_nvidia(self, input_path: str, output_path: str,
                      codec: str, quality: str, preset: str) -> str:
        """NVIDIA NVENCエンコード"""
        codec_map = {
            "h264": "h264_nvenc",
            "h265": "hevc_nvenc",
            "av1": "av1_nvenc"
        }

        quality_map = {
            "low": "30",
            "medium": "23",
            "high": "18",
            "ultra": "15"
        }

        video_codec = codec_map.get(codec, "h264_nvenc")
        cq_value = quality_map.get(quality, "18")

        cmd = [
            FFMPEG_PATH, "-y",
            "-hwaccel", "cuda",
            "-i", str(input_path),
            "-c:v", video_codec,
            "-preset", preset,
            "-cq", cq_value,
            "-rc", "vbr",
            "-b:v", "0",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"NVIDIA NVENC encoding completed: {output_path}")
        return str(output_path)

    def _encode_amd(self, input_path: str, output_path: str,
                   codec: str, quality: str) -> str:
        """AMD AMFエンコード"""
        codec_map = {
            "h264": "h264_amf",
            "h265": "hevc_amf"
        }

        video_codec = codec_map.get(codec, "h264_amf")

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-c:v", video_codec,
            "-quality", "quality",
            "-rc", "vbr_hq",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return str(output_path)

    def _encode_intel(self, input_path: str, output_path: str,
                     codec: str, quality: str) -> str:
        """Intel QSVエンコード"""
        codec_map = {
            "h264": "h264_qsv",
            "h265": "hevc_qsv"
        }

        video_codec = codec_map.get(codec, "h264_qsv")

        cmd = [
            FFMPEG_PATH, "-y",
            "-hwaccel", "qsv",
            "-i", str(input_path),
            "-c:v", video_codec,
            "-preset", "slow",
            "-global_quality", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return str(output_path)

    def _encode_cpu(self, input_path: str, output_path: str,
                   codec: str, quality: str) -> str:
        """CPUエンコード (フォールバック)"""
        codec_map = {
            "h264": "libx264",
            "h265": "libx265",
            "av1": "libaom-av1"
        }

        quality_map = {
            "low": "28",
            "medium": "23",
            "high": "18",
            "ultra": "15"
        }

        video_codec = codec_map.get(codec, "libx264")
        crf_value = quality_map.get(quality, "18")

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-c:v", video_codec,
            "-preset", "slow",
            "-crf", crf_value,
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return str(output_path)
