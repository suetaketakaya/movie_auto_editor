"""
Video Editor Module
FFmpegを使用した動画編集
"""

import subprocess
import logging
import asyncio
from typing import List, Dict
from pathlib import Path
import json
import shutil
import os

logger = logging.getLogger(__name__)

# FFmpegの場所を検出
def get_ffmpeg_path():
    """FFmpegの実行可能ファイルパスを取得"""
    # まずPATHから検索
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # Windowsの一般的なインストール場所
    possible_paths = [
        r"C:\Users\suetake\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"Found FFmpeg at: {path}")
            return path

    # デフォルト（PATHに期待）
    return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_path()
FFPROBE_PATH = FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe") if "ffmpeg.exe" in FFMPEG_PATH else "ffprobe"


class VideoEditor:
    """FFmpegを使用した動画編集クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.codec = config["export"]["codec"]
        self.crf = config["export"]["crf"]
        self.preset = config["export"]["preset"]
        self.maintain_fps = config["export"]["maintain_fps"]

    async def create_highlight(self, input_video: str, clips: List[Dict], output_path: str) -> str:
        """
        ハイライト動画を作成

        Args:
            input_video: 入力動画ファイルパス
            clips: クリップ情報のリスト [{"start": 10.0, "end": 25.0}, ...]
            output_path: 出力動画ファイルパス

        Returns:
            出力動画ファイルパス
        """
        if not clips:
            logger.warning("No clips to create highlight video")
            # クリップがない場合は元動画をコピー
            return await self._copy_video(input_video, output_path)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_highlight_sync, input_video, clips, output_path)

    def _create_highlight_sync(self, input_video: str, clips: List[Dict], output_path: str) -> str:
        """同期版のハイライト作成"""
        logger.info(f"Creating highlight video with {len(clips)} clips")

        # 一時ファイルリスト
        temp_clips = []

        try:
            # 各クリップを個別に抽出
            for i, clip in enumerate(clips):
                start = clip["start"]
                end = clip["end"]
                duration = end - start

                temp_clip_path = Path(output_path).parent / f"temp_clip_{i:03d}.mp4"

                logger.info(f"Extracting clip {i+1}/{len(clips)}: {start:.2f}s - {end:.2f}s")

                # FFmpegコマンドを構築
                cmd = self._build_extract_command(input_video, start, duration, temp_clip_path)

                # FFmpegを実行
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    logger.error(f"FFmpeg error: {result.stderr}")
                    raise RuntimeError(f"FFmpeg failed for clip {i}")

                temp_clips.append(str(temp_clip_path))

            # クリップを結合
            if len(temp_clips) == 1:
                # クリップが1つだけの場合はリネームするだけ
                Path(temp_clips[0]).rename(output_path)
            else:
                # 複数のクリップを結合
                self._concatenate_clips(temp_clips, output_path)

            logger.info(f"Highlight video created: {output_path}")

            return str(output_path)

        finally:
            # 一時ファイルを削除
            for temp_clip in temp_clips:
                try:
                    if Path(temp_clip).exists() and str(temp_clip) != str(output_path):
                        Path(temp_clip).unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_clip}: {e}")

    def _build_extract_command(self, input_video: str, start: float, duration: float, output: Path) -> List[str]:
        """クリップ抽出用のFFmpegコマンドを構築"""
        cmd = [
            FFMPEG_PATH,
            "-y",  # 上書き
            "-ss", str(start),  # 開始位置
            "-i", input_video,  # 入力ファイル
            "-t", str(duration),  # 長さ
            "-c:v", self.codec,  # ビデオコーデック
            "-crf", str(self.crf),  # 品質
            "-preset", self.preset,  # プリセット
            "-c:a", "aac",  # オーディオコーデック
            "-b:a", "192k",  # オーディオビットレート
        ]

        # FPSを維持
        if self.maintain_fps:
            cmd.extend(["-r", "60"])  # デフォルト60fps（元動画から取得する方が良い）

        cmd.append(str(output))

        return cmd

    def _concatenate_clips(self, clip_paths: List[str], output_path: str):
        """複数のクリップを結合"""
        logger.info(f"Concatenating {len(clip_paths)} clips")

        # concat用のファイルリストを作成
        concat_file = Path(output_path).parent / "concat_list.txt"

        logger.info(f"Creating concat list at: {concat_file.absolute()}")

        with open(concat_file, "w", encoding="utf-8") as f:
            for clip_path in clip_paths:
                # FFmpegのconcat形式 - 絶対パスを使用してパス重複を回避
                abs_path = Path(clip_path).absolute()
                logger.info(f"Adding to concat list: {abs_path}")
                f.write(f"file '{abs_path}'\n")

        try:
            # FFmpegでconcat
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",  # 再エンコードなし
                str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"FFmpeg concatenation error: {result.stderr}")
                raise RuntimeError("FFmpeg concatenation failed")

        finally:
            # concat listファイルを削除
            if concat_file.exists():
                concat_file.unlink()

    async def _copy_video(self, input_path: str, output_path: str) -> str:
        """動画をコピー"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._copy_video_sync, input_path, output_path)

    def _copy_video_sync(self, input_path: str, output_path: str) -> str:
        """同期版の動画コピー"""
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-c", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg copy failed: {result.stderr}")

        return str(output_path)

    def get_video_metadata(self, video_path: str) -> Dict:
        """動画のメタデータを取得"""
        cmd = [
            FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFprobe failed: {result.stderr}")

        return json.loads(result.stdout)

    def create_9_16_crop(self, input_video: str, output_path: str, position: str = "center") -> str:
        """
        9:16のショート動画用にクロップ

        Args:
            input_video: 入力動画
            output_path: 出力パス
            position: クロップ位置 ("center", "top", "bottom")
        """
        # 動画の解像度を取得
        metadata = self.get_video_metadata(input_video)
        video_stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")

        width = int(video_stream["width"])
        height = int(video_stream["height"])

        # 9:16の幅を計算
        target_width = int(height * 9 / 16)

        # クロップ位置を計算
        if position == "center":
            x = (width - target_width) // 2
        elif position == "top":
            x = (width - target_width) // 2
        else:  # bottom
            x = (width - target_width) // 2

        # FFmpegコマンド
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_video,
            "-vf", f"crop={target_width}:{height}:{x}:0",
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", self.preset,
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg crop failed: {result.stderr}")

        return str(output_path)
