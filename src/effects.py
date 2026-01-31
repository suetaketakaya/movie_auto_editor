"""
Visual Effects Module
動画への視覚エフェクト適用
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional
import os
import shutil

logger = logging.getLogger(__name__)

# FFmpegパスを取得
def get_ffmpeg_path():
    """FFmpegの実行可能ファイルパスを取得"""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    possible_paths = [
        r"C:\Users\suetake\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_path()


class VisualEffects:
    """視覚エフェクトを適用するクラス"""

    def __init__(self, config: dict):
        self.config = config
        self.effects_config = config.get("effects", {})

    def apply_transition(self, clip1_path: str, clip2_path: str, output_path: str,
                        transition_type: str = "fade", duration: float = 0.5) -> str:
        """
        2つのクリップ間にトランジション効果を適用

        Args:
            clip1_path: 最初のクリップ
            clip2_path: 次のクリップ
            output_path: 出力パス
            transition_type: fade, wipeleft, wiperight, slideleft, slideright, etc.
            duration: トランジションの長さ（秒）
        """
        logger.info(f"Applying {transition_type} transition between clips")

        # xfadeフィルターを使用
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", clip1_path,
            "-i", clip2_path,
            "-filter_complex",
            f"[0:v][1:v]xfade=transition={transition_type}:duration={duration}:offset=0[vout];[0:a][1:a]acrossfade=d={duration}[aout]",
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-c:a", "aac",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Transition effect failed: {result.stderr}")
            raise RuntimeError("Transition effect failed")

        return str(output_path)

    def apply_slow_motion(self, input_path: str, output_path: str,
                         start_time: float, end_time: float, speed: float = 0.5) -> str:
        """
        指定した区間にスローモーション効果を適用

        Args:
            input_path: 入力動画
            output_path: 出力パス
            start_time: スローモーション開始時間（秒）
            end_time: スローモーション終了時間（秒）
            speed: 速度倍率（0.5 = 半分の速度）
        """
        logger.info(f"Applying slow motion from {start_time}s to {end_time}s at {speed}x speed")

        # setptsフィルターでスローモーション
        pts_factor = 1.0 / speed

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-filter_complex",
            f"[0:v]setpts={pts_factor}*PTS[v];[0:a]atempo={speed}[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-c:a", "aac",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Slow motion effect failed: {result.stderr}")
            raise RuntimeError("Slow motion effect failed")

        return str(output_path)

    def apply_zoom(self, input_path: str, output_path: str,
                   zoom_factor: float = 1.5, duration: float = 2.0) -> str:
        """
        ズームイン効果を適用

        Args:
            input_path: 入力動画
            output_path: 出力パス
            zoom_factor: ズーム倍率
            duration: ズームにかける時間（秒）
        """
        logger.info(f"Applying zoom effect (factor: {zoom_factor})")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-filter_complex",
            f"[0:v]zoompan=z='min(zoom+0.0015,{zoom_factor})':d={int(duration*30)}:s=1920x1080[v]",
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Zoom effect failed: {result.stderr}")
            raise RuntimeError("Zoom effect failed")

        return str(output_path)

    def apply_color_grading(self, input_path: str, output_path: str,
                           preset: str = "cinematic") -> str:
        """
        カラーグレーディングを適用

        Args:
            input_path: 入力動画
            output_path: 出力パス
            preset: cinematic, vibrant, warm, cool, desaturated
        """
        logger.info(f"Applying color grading: {preset}")

        # プリセットに応じたフィルター設定
        color_filters = {
            "cinematic": "eq=contrast=1.2:brightness=0.05:saturation=0.9,curves=vintage",
            "vibrant": "eq=contrast=1.1:saturation=1.3",
            "warm": "eq=contrast=1.05:saturation=1.1,colortemperature=7000",
            "cool": "eq=contrast=1.05:saturation=1.1,colortemperature=3000",
            "desaturated": "eq=saturation=0.7:contrast=1.15"
        }

        filter_str = color_filters.get(preset, color_filters["cinematic"])

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", filter_str,
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Color grading failed: {result.stderr}")
            raise RuntimeError("Color grading failed")

        return str(output_path)

    def apply_vignette(self, input_path: str, output_path: str,
                       intensity: float = 0.3) -> str:
        """
        ビネット効果（画面端を暗く）を適用

        Args:
            input_path: 入力動画
            output_path: 出力パス
            intensity: 強度（0.0 - 1.0）
        """
        logger.info(f"Applying vignette effect (intensity: {intensity})")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", f"vignette=PI/4*{intensity}",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Vignette effect failed: {result.stderr}")
            raise RuntimeError("Vignette effect failed")

        return str(output_path)

    def apply_shake(self, input_path: str, output_path: str,
                    intensity: int = 5) -> str:
        """
        画面揺れ効果を適用（アクションシーン用）

        Args:
            input_path: 入力動画
            output_path: 出力パス
            intensity: 揺れの強度（ピクセル数）
        """
        logger.info(f"Applying shake effect (intensity: {intensity})")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", f"crop=in_w-{intensity*2}:in_h-{intensity*2}:x={intensity}*sin(2*PI*t):y={intensity}*cos(2*PI*t)",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Shake effect failed: {result.stderr}")
            raise RuntimeError("Shake effect failed")

        return str(output_path)

    def apply_chromatic_aberration(self, input_path: str, output_path: str) -> str:
        """
        色収差効果を適用（グリッチ風）

        Args:
            input_path: 入力動画
            output_path: 出力パス
        """
        logger.info("Applying chromatic aberration effect")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-filter_complex",
            "[0:v]split=3[r][g][b];"
            "[r]lutrgb=r=val:g=0:b=0[red];"
            "[g]lutrgb=r=0:g=val:b=0,pad=iw+4:ih:2:0[green];"
            "[b]lutrgb=r=0:g=0:b=val,pad=iw+4:ih:2:0[blue];"
            "[red][green]blend=all_mode=addition[rg];"
            "[rg][blue]blend=all_mode=addition[v]",
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Chromatic aberration failed: {result.stderr}")
            raise RuntimeError("Chromatic aberration failed")

        return str(output_path)
