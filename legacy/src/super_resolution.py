"""
AI Super Resolution Module (Real-ESRGAN)
AI超解像モジュール - 動画の高解像度化
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# FFmpeg path
FFMPEG_PATH = "ffmpeg"


class SuperResolution:
    """AI超解像クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.sr_config = config.get("super_resolution", {})
        self.enabled = self.sr_config.get("enable", True)

    def upscale_video(self, input_path: str, output_path: str,
                     scale: int = 2, model: str = "realesrgan-x4plus") -> str:
        """
        動画を超解像アップスケール

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス
            scale: スケール倍率 (2, 4)
            model: 使用モデル (realesrgan-x4plus, realesrgan-x4plus-anime)

        Returns:
            出力ファイルパス
        """
        if not self.enabled:
            logger.info("Super resolution is disabled, copying original")
            return input_path

        logger.info(f"Starting AI super resolution: {input_path} -> {output_path}")
        logger.info(f"Scale: {scale}x, Model: {model}")

        try:
            # Real-ESRGANがインストールされていればそれを使用
            # なければFFmpegのスケーリングフィルターを使用
            if self._check_realesrgan_available():
                return self._upscale_with_realesrgan(input_path, output_path, scale, model)
            else:
                logger.warning("Real-ESRGAN not available, using FFmpeg lanczos upscaling")
                return self._upscale_with_ffmpeg(input_path, output_path, scale)

        except Exception as e:
            logger.error(f"Super resolution failed: {e}")
            return input_path

    def _check_realesrgan_available(self) -> bool:
        """Real-ESRGANの利用可能性チェック"""
        try:
            result = subprocess.run(
                ["realesrgan-ncnn-vulkan", "-h"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _upscale_with_realesrgan(self, input_path: str, output_path: str,
                                scale: int, model: str) -> str:
        """Real-ESRGANを使用した超解像"""
        logger.info("Using Real-ESRGAN for super resolution")

        # 一時ディレクトリ作成
        temp_frames_dir = Path("temp_sr_frames")
        temp_upscaled_dir = Path("temp_sr_upscaled")
        temp_frames_dir.mkdir(exist_ok=True)
        temp_upscaled_dir.mkdir(exist_ok=True)

        try:
            # 1. 動画をフレーム分解
            logger.info("Extracting frames for upscaling...")
            extract_cmd = [
                FFMPEG_PATH, "-i", str(input_path),
                "-qscale:v", "1",
                str(temp_frames_dir / "frame_%06d.png")
            ]
            subprocess.run(extract_cmd, check=True, capture_output=True)

            # 2. Real-ESRGANで各フレームをアップスケール
            logger.info("Upscaling frames with Real-ESRGAN...")
            realesrgan_cmd = [
                "realesrgan-ncnn-vulkan",
                "-i", str(temp_frames_dir),
                "-o", str(temp_upscaled_dir),
                "-n", model,
                "-s", str(scale),
                "-f", "png"
            ]
            subprocess.run(realesrgan_cmd, check=True)

            # 3. フレームを動画に再結合
            logger.info("Reassembling upscaled frames to video...")
            reassemble_cmd = [
                FFMPEG_PATH, "-y",
                "-framerate", "60",
                "-i", str(temp_upscaled_dir / "frame_%06d.png"),
                "-i", str(input_path),  # オーディオ用
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                "-c:a", "copy",
                str(output_path)
            ]
            subprocess.run(reassemble_cmd, check=True, capture_output=True)

            logger.info("Real-ESRGAN upscaling completed successfully")
            return str(output_path)

        finally:
            # 一時ファイル削除
            import shutil
            if temp_frames_dir.exists():
                shutil.rmtree(temp_frames_dir)
            if temp_upscaled_dir.exists():
                shutil.rmtree(temp_upscaled_dir)

    def _upscale_with_ffmpeg(self, input_path: str, output_path: str, scale: int) -> str:
        """FFmpegのLanczosフィルターを使用した高品質アップスケール"""
        logger.info(f"Using FFmpeg Lanczos {scale}x upscaling")

        # 元の解像度を取得
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(input_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(','))

        new_width = width * scale
        new_height = height * scale

        # Lanczosフィルターでアップスケール
        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-vf", f"scale={new_width}:{new_height}:flags=lanczos",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"FFmpeg upscaling completed: {new_width}x{new_height}")
        return str(output_path)

    def enhance_face_quality(self, input_path: str, output_path: str) -> str:
        """
        顔の画質を特別に強化 (GFPGAN)

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス

        Returns:
            出力ファイルパス
        """
        if not self.sr_config.get("enhance_faces", False):
            return input_path

        logger.info("Enhancing face quality with GFPGAN")

        # GFPGAN利用可能性チェック
        if not self._check_gfpgan_available():
            logger.warning("GFPGAN not available, skipping face enhancement")
            return input_path

        # 実装は省略 (GFPGAN統合が必要)
        # 本格実装にはGFPGANのPythonパッケージが必要

        return input_path

    def _check_gfpgan_available(self) -> bool:
        """GFPGANの利用可能性チェック"""
        try:
            import gfpgan
            return True
        except ImportError:
            return False

    def denoise_and_sharpen(self, input_path: str, output_path: str) -> str:
        """
        ノイズ除去とシャープネス向上

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス

        Returns:
            出力ファイルパス
        """
        logger.info("Applying denoise and sharpening filters")

        # hqdn3d (高品質ノイズ除去) + unsharp (シャープネス)
        filter_complex = "hqdn3d=1.5:1.5:6:6,unsharp=5:5:1.0:5:5:0.0"

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-vf", filter_complex,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("Denoise and sharpening completed")
        return str(output_path)
