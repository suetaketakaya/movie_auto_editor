"""
AI Audio Enhancement Module
AI音声強化モジュール - ノイズキャンセル、音声クリアネス向上
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)
FFMPEG_PATH = "ffmpeg"


class AudioEnhancer:
    """AI音声強化クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.audio_config = config.get("audio_enhancer", {})

    def remove_background_noise(self, input_path: str, output_path: str) -> str:
        """背景ノイズ除去 (RNNoise風)"""
        logger.info("Removing background noise from audio")

        # highpass + lowpass + afftdn (FFTベースノイズ除去)
        filter_str = "highpass=f=200,lowpass=f=3000,afftdn=nf=-25"

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-af", filter_str,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("Background noise removal completed")
        return str(output_path)

    def enhance_voice_clarity(self, input_path: str, output_path: str) -> str:
        """音声クリアネス向上"""
        logger.info("Enhancing voice clarity")

        # EQ + compressor + gate
        filter_str = (
            "equalizer=f=300:width_type=o:width=2:g=3,"
            "equalizer=f=3000:width_type=o:width=2:g=5,"
            "acompressor=threshold=-20dB:ratio=4:attack=5:release=50,"
            "agate=threshold=-50dB:ratio=2"
        )

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-af", filter_str,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return str(output_path)
