"""
Text Overlay Module
動画へのテキストオーバーレイ
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


class TextOverlay:
    """テキストオーバーレイクラス"""

    def __init__(self, config: dict):
        self.config = config
        self.text_config = config.get("text_overlay", {})

    def add_kill_counter(self, input_path: str, output_path: str,
                        kill_timestamps: List[float]) -> str:
        """
        キル数カウンターを追加

        Args:
            input_path: 入力動画
            output_path: 出力パス
            kill_timestamps: キルが発生したタイムスタンプのリスト
        """
        logger.info(f"Adding kill counter: {len(kill_timestamps)} kills")

        # キルカウントのタイムライン作成
        drawtext_filters = []

        for i, timestamp in enumerate(kill_timestamps, 1):
            # 各キルから3秒間カウンターを表示
            start = timestamp
            end = timestamp + 3.0

            filter_str = (
                f"drawtext=text='{i} KILLS':"
                f"fontfile=/Windows/Fonts/impact.ttf:fontsize=48:"
                f"fontcolor=white:borderw=3:bordercolor=black:"
                f"x=(w-text_w)/2:y=50:"
                f"enable='between(t,{start},{end})'"
            )
            drawtext_filters.append(filter_str)

        # すべてのdrawtextフィルターを結合
        full_filter = ",".join(drawtext_filters) if drawtext_filters else "null"

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", full_filter,
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Kill counter overlay failed: {result.stderr}")
            raise RuntimeError("Kill counter overlay failed")

        return str(output_path)

    def add_text_popup(self, input_path: str, output_path: str,
                      text: str, timestamp: float, duration: float = 2.0,
                      position: str = "center") -> str:
        """
        テキストポップアップを追加（"TRIPLE KILL!"など）

        Args:
            input_path: 入力動画
            output_path: 出力パス
            text: 表示するテキスト
            timestamp: 表示開始時間
            duration: 表示時間
            position: top, center, bottom
        """
        logger.info(f"Adding text popup: '{text}' at {timestamp}s")

        # 位置設定
        y_positions = {
            "top": "100",
            "center": "(h-text_h)/2",
            "bottom": "h-text_h-100"
        }
        y_pos = y_positions.get(position, y_positions["center"])

        # アニメーション効果（フェードイン・アウト + スケール）
        end = timestamp + duration
        fade_duration = 0.3

        filter_str = (
            f"drawtext=text='{text}':"
            f"fontfile=/Windows/Fonts/impact.ttf:fontsize=72:"
            f"fontcolor=yellow:borderw=5:bordercolor=black:"
            f"x=(w-text_w)/2:y={y_pos}:"
            f"alpha='if(lt(t,{timestamp+fade_duration}),(t-{timestamp})/{fade_duration},"
            f"if(gt(t,{end-fade_duration}),({end}-t)/{fade_duration},1))':"
            f"enable='between(t,{timestamp},{end})'"
        )

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
            logger.error(f"Text popup failed: {result.stderr}")
            raise RuntimeError("Text popup failed")

        return str(output_path)

    def add_timestamp_overlay(self, input_path: str, output_path: str) -> str:
        """
        タイムスタンプオーバーレイを追加

        Args:
            input_path: 入力動画
            output_path: 出力パス
        """
        logger.info("Adding timestamp overlay")

        filter_str = (
            "drawtext=text='%{pts\\:hms}':"
            "fontfile=/Windows/Fonts/consola.ttf:fontsize=24:"
            "fontcolor=white:borderw=2:bordercolor=black:"
            "x=w-text_w-20:y=20"
        )

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
            logger.error(f"Timestamp overlay failed: {result.stderr}")
            raise RuntimeError("Timestamp overlay failed")

        return str(output_path)

    def add_custom_text(self, input_path: str, output_path: str,
                       text: str, x: int = 50, y: int = 50,
                       font_size: int = 36, color: str = "white") -> str:
        """
        カスタムテキストを追加

        Args:
            input_path: 入力動画
            output_path: 出力パス
            text: 表示するテキスト
            x, y: 位置（ピクセル）
            font_size: フォントサイズ
            color: フォントカラー
        """
        logger.info(f"Adding custom text: '{text}' at ({x}, {y})")

        filter_str = (
            f"drawtext=text='{text}':"
            f"fontfile=/Windows/Fonts/arial.ttf:fontsize={font_size}:"
            f"fontcolor={color}:borderw=2:bordercolor=black:"
            f"x={x}:y={y}"
        )

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
            logger.error(f"Custom text overlay failed: {result.stderr}")
            raise RuntimeError("Custom text overlay failed")

        return str(output_path)

    def add_subtitle(self, input_path: str, output_path: str,
                    subtitle_file: str) -> str:
        """
        字幕ファイル（SRT）を動画に焼き込み

        Args:
            input_path: 入力動画
            output_path: 出力パス
            subtitle_file: SRT字幕ファイルパス
        """
        logger.info(f"Adding subtitles from: {subtitle_file}")

        # Windowsパスのエスケープ
        subtitle_path = subtitle_file.replace("\\", "/").replace(":", "\\:")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", f"subtitles={subtitle_path}",
            "-c:v", "libx264",
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Subtitle overlay failed: {result.stderr}")
            raise RuntimeError("Subtitle overlay failed")

        return str(output_path)

    def add_progress_bar(self, input_path: str, output_path: str,
                        total_duration: float) -> str:
        """
        プログレスバーを追加

        Args:
            input_path: 入力動画
            output_path: 出力パス
            total_duration: 動画の総再生時間
        """
        logger.info("Adding progress bar")

        filter_str = (
            "drawbox=x=50:y=h-80:w=w-100:h=10:color=gray@0.5:t=fill,"
            f"drawbox=x=50:y=h-80:w='(w-100)*t/{total_duration}':h=10:color=red:t=fill"
        )

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
            logger.error(f"Progress bar overlay failed: {result.stderr}")
            raise RuntimeError("Progress bar overlay failed")

        return str(output_path)
