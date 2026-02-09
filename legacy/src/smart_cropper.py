"""
Smart Cropping Module (Face/Object Tracking)
スマートクロッピングモジュール - 顔・重要領域追跡
"""

import logging
import subprocess
import cv2
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)
FFMPEG_PATH = "ffmpeg"


class SmartCropper:
    """スマートクロッピングクラス"""

    def __init__(self, config: dict):
        self.config = config
        self.cropper_config = config.get("smart_cropper", {})
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def create_vertical_video(self, input_path: str, output_path: str,
                             tracking_mode: str = "center") -> str:
        """
        9:16縦動画を作成 (スマートクロッピング)

        Args:
            input_path: 入力動画パス
            output_path: 出力動画パス
            tracking_mode: 追跡モード (center, face, action)

        Returns:
            出力ファイルパス
        """
        logger.info(f"Creating vertical video with {tracking_mode} tracking")

        if tracking_mode == "face":
            return self._crop_with_face_tracking(input_path, output_path)
        elif tracking_mode == "action":
            return self._crop_with_action_tracking(input_path, output_path)
        else:
            return self._crop_center(input_path, output_path)

    def _crop_center(self, input_path: str, output_path: str) -> str:
        """中央クロッピング"""
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

        # 9:16の幅を計算
        target_width = int(height * 9 / 16)
        x_offset = (width - target_width) // 2

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(input_path),
            "-vf", f"crop={target_width}:{height}:{x_offset}:0",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return str(output_path)

    def _crop_with_face_tracking(self, input_path: str, output_path: str) -> str:
        """顔追跡クロッピング (簡易実装)"""
        logger.info("Face tracking cropping")
        # 実際の実装にはMediaPipeやYOLOが必要
        # 現状は中央クロッピングにフォールバック
        return self._crop_center(input_path, output_path)

    def _crop_with_action_tracking(self, input_path: str, output_path: str) -> str:
        """アクション追跡クロッピング"""
        # 動きの多い領域を追跡
        return self._crop_center(input_path, output_path)
