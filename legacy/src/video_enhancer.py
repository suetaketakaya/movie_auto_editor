"""
Video Enhancement Module
動画品質向上モジュール - ノイズ除去、手ブレ補正、LUTカラーグレーディング
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# FFmpeg path
FFMPEG_PATH = "ffmpeg"


class VideoEnhancer:
    """動画品質向上クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.enhancer_config = config.get("video_enhancer", {})

    def apply_professional_denoise(self, input_path: str, output_path: str,
                                   strength: str = "medium") -> str:
        """
        プロフェッショナルノイズ除去

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス
            strength: ノイズ除去強度 (light, medium, strong)

        Returns:
            出力ファイルパス
        """
        logger.info(f"Applying professional denoise: {strength}")

        # hqdn3d (高品質3Dノイズ除去) + nlmeans (非局所平均フィルター)
        denoise_presets = {
            "light": "hqdn3d=1.5:1.5:6:6",
            "medium": "hqdn3d=2.0:2.0:8:8,nlmeans=s=1.5:p=7:r=15",
            "strong": "hqdn3d=3.0:3.0:10:10,nlmeans=s=3.0:p=7:r=15"
        }

        filter_str = denoise_presets.get(strength, denoise_presets["medium"])

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("Professional denoise completed")
        return str(output_path)

    def stabilize_video(self, input_path: str, output_path: str,
                       smoothing: int = 10) -> str:
        """
        手ブレ補正 (ビデオスタビライゼーション)

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス
            smoothing: スムージング強度 (1-100)

        Returns:
            出力ファイルパス
        """
        logger.info(f"Stabilizing video with smoothing: {smoothing}")

        # vidstabdetect + vidstabtransform (2パス処理)
        transforms_file = Path("transforms.trf")

        try:
            # パス1: モーション検出
            detect_cmd = [
                FFMPEG_PATH, "-y", "-i", str(input_path),
                "-vf", f"vidstabdetect=shakiness=10:accuracy=15:result={transforms_file}",
                "-f", "null", "-"
            ]
            subprocess.run(detect_cmd, check=True, capture_output=True)

            # パス2: スタビライゼーション適用
            transform_cmd = [
                FFMPEG_PATH, "-y", "-i", str(input_path),
                "-vf", f"vidstabtransform=input={transforms_file}:smoothing={smoothing}:zoom=1:optalgo=gauss",
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18",
                "-c:a", "copy",
                str(output_path)
            ]
            subprocess.run(transform_cmd, check=True, capture_output=True)

            logger.info("Video stabilization completed")
            return str(output_path)

        finally:
            # 一時ファイル削除
            if transforms_file.exists():
                transforms_file.unlink()

    def apply_lut_grading(self, input_path: str, output_path: str,
                         lut_file: Optional[str] = None,
                         preset: str = "cinematic") -> str:
        """
        LUTカラーグレーディング適用

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス
            lut_file: LUTファイルパス (.cube)
            preset: プリセット名 (cinematic, teal_orange, vintage, etc.)

        Returns:
            出力ファイルパス
        """
        logger.info(f"Applying LUT color grading: {preset}")

        if lut_file and Path(lut_file).exists():
            # 外部LUTファイルを使用
            filter_str = f"lut3d={lut_file}"
        else:
            # プリセットLUTを使用 (FFmpegの組み込みフィルター)
            lut_presets = {
                "cinematic": "eq=contrast=1.2:brightness=0.05:saturation=0.9,curves=vintage",
                "teal_orange": "curves=r='0/0 0.5/0.4 1/1':g='0/0 0.5/0.5 1/1':b='0/0.1 0.5/0.6 1/1'",
                "vintage": "curves=vintage,eq=saturation=0.8:contrast=1.15",
                "warm": "eq=contrast=1.05:saturation=1.1,colortemperature=7000",
                "cool": "eq=contrast=1.05:saturation=1.1,colortemperature=3000",
                "vibrant": "eq=contrast=1.15:saturation=1.4:gamma=1.05",
                "moody": "curves=preset=darker:vintage,eq=saturation=0.7",
                "bleach_bypass": "eq=contrast=1.3:saturation=0.6,curves=strong_contrast"
            }

            filter_str = lut_presets.get(preset, lut_presets["cinematic"])

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"LUT grading completed: {preset}")
        return str(output_path)

    def add_film_grain(self, input_path: str, output_path: str,
                      strength: float = 0.3) -> str:
        """
        フィルムグレイン効果追加 (シネマティック感)

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス
            strength: グレイン強度 (0.0-1.0)

        Returns:
            出力ファイルパス
        """
        logger.info(f"Adding film grain effect: {strength}")

        # ノイズフィルターでグレイン効果
        filter_str = f"noise=alls={int(strength * 20)}:allf=t+u"

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("Film grain effect completed")
        return str(output_path)

    def enhance_sharpness(self, input_path: str, output_path: str,
                         amount: float = 1.0) -> str:
        """
        シャープネス向上

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス
            amount: シャープネス量 (0.5-2.0)

        Returns:
            出力ファイルパス
        """
        logger.info(f"Enhancing sharpness: {amount}")

        # unsharp フィルター
        filter_str = f"unsharp=5:5:{amount}:5:5:0.0"

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("Sharpness enhancement completed")
        return str(output_path)

    def auto_levels_correction(self, input_path: str, output_path: str) -> str:
        """
        自動レベル補正 (明るさ・コントラスト最適化)

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス

        Returns:
            出力ファイルパス
        """
        logger.info("Applying auto levels correction")

        # histogramの自動均等化
        filter_str = "histeq=strength=0.8,eq=gamma=1.1"

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("Auto levels correction completed")
        return str(output_path)

    def apply_all_enhancements(self, input_path: str, output_path: str) -> str:
        """
        すべての品質向上処理を適用

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス

        Returns:
            出力ファイルパス
        """
        logger.info("Applying all video enhancements")

        config = self.enhancer_config

        # フィルターチェーンを構築
        filters = []

        # 1. ノイズ除去
        if config.get("denoise", {}).get("enable", True):
            strength = config.get("denoise", {}).get("strength", "medium")
            denoise_presets = {
                "light": "hqdn3d=1.5:1.5:6:6",
                "medium": "hqdn3d=2.0:2.0:8:8",
                "strong": "hqdn3d=3.0:3.0:10:10"
            }
            filters.append(denoise_presets.get(strength, "hqdn3d=2.0:2.0:8:8"))

        # 2. シャープネス
        if config.get("sharpen", {}).get("enable", True):
            amount = config.get("sharpen", {}).get("amount", 1.0)
            filters.append(f"unsharp=5:5:{amount}:5:5:0.0")

        # 3. カラーグレーディング
        if config.get("lut", {}).get("enable", True):
            preset = config.get("lut", {}).get("preset", "cinematic")
            lut_presets = {
                "cinematic": "eq=contrast=1.2:brightness=0.05:saturation=0.9,curves=vintage",
                "teal_orange": "curves=r='0/0 0.5/0.4 1/1':g='0/0 0.5/0.5 1/1':b='0/0.1 0.5/0.6 1/1'",
                "vintage": "curves=vintage,eq=saturation=0.8:contrast=1.15",
                "warm": "eq=contrast=1.05:saturation=1.1,colortemperature=7000",
                "vibrant": "eq=contrast=1.15:saturation=1.4:gamma=1.05"
            }
            filters.append(lut_presets.get(preset, lut_presets["cinematic"]))

        # 4. フィルムグレイン (オプション)
        if config.get("grain", {}).get("enable", False):
            strength = config.get("grain", {}).get("strength", 0.3)
            filters.append(f"noise=alls={int(strength * 20)}:allf=t+u")

        # フィルターチェーンを結合
        filter_complex = ",".join(filters) if filters else "copy"

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
        logger.info("All video enhancements completed")
        return str(output_path)
