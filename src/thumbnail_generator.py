"""
Thumbnail Generator Module
サムネイル画像生成とSNS最適化
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional
import os
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

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


class ThumbnailGenerator:
    """サムネイル生成クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.thumb_config = config.get("thumbnail", {})

    def extract_best_frame(self, video_path: str, timestamp: float, output_path: str) -> str:
        """
        指定したタイムスタンプからフレームを抽出

        Args:
            video_path: 入力動画
            timestamp: タイムスタンプ
            output_path: 出力パス
        """
        logger.info(f"Extracting frame at {timestamp}s for thumbnail")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",  # 高品質
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Frame extraction failed: {result.stderr}")
            raise RuntimeError("Frame extraction failed")

        return str(output_path)

    def create_youtube_thumbnail(self, frame_path: str, output_path: str,
                                 title_text: str = "", kill_count: int = 0) -> str:
        """
        YouTubeサムネイル作成（1280x720）

        Args:
            frame_path: 元フレーム画像
            output_path: 出力パス
            title_text: タイトルテキスト
            kill_count: キル数
        """
        logger.info("Creating YouTube thumbnail")

        # 画像を読み込み
        img = Image.open(frame_path)
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)

        # コントラストと彩度を上げる
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)

        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.2)

        # ビネット効果
        img = self._apply_vignette_pil(img)

        # 描画オブジェクト
        draw = ImageDraw.Draw(img)

        # フォント設定（Windowsフォント）
        try:
            title_font = ImageFont.truetype("C:/Windows/Fonts/impact.ttf", 80)
            count_font = ImageFont.truetype("C:/Windows/Fonts/impact.ttf", 120)
        except:
            title_font = ImageFont.load_default()
            count_font = ImageFont.load_default()

        # タイトルテキスト（下部）
        if title_text:
            text_bbox = draw.textbbox((0, 0), title_text, font=title_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            x = (1280 - text_width) // 2
            y = 600

            # 影
            draw.text((x + 5, y + 5), title_text, fill=(0, 0, 0), font=title_font)
            # 本文
            draw.text((x, y), title_text, fill=(255, 255, 0), font=title_font)

        # キル数表示（右上）
        if kill_count > 0:
            count_text = f"{kill_count} KILLS"
            count_bbox = draw.textbbox((0, 0), count_text, font=count_font)
            count_width = count_bbox[2] - count_bbox[0]

            x = 1280 - count_width - 50
            y = 50

            # 背景矩形
            padding = 20
            draw.rectangle(
                [x - padding, y - padding, x + count_width + padding, y + 100 + padding],
                fill=(0, 0, 0, 180)
            )

            # テキスト
            draw.text((x + 3, y + 3), count_text, fill=(0, 0, 0), font=count_font)
            draw.text((x, y), count_text, fill=(255, 50, 50), font=count_font)

        # 保存
        img.save(output_path, quality=95)
        logger.info(f"YouTube thumbnail created: {output_path}")

        return str(output_path)

    def create_short_video(self, input_path: str, output_path: str,
                          position: str = "center") -> str:
        """
        9:16縦型ショート動画を作成

        Args:
            input_path: 入力動画（16:9）
            output_path: 出力パス
            position: クロップ位置（center, left, right）
        """
        logger.info(f"Creating short video (9:16) with position: {position}")

        # 入力動画の解像度を取得
        probe_cmd = [
            FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe"),
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            input_path
        ]

        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        width, height = map(int, result.stdout.strip().split('x'))

        # 9:16の幅を計算
        target_width = int(height * 9 / 16)

        # クロップ位置
        positions = {
            "center": (width - target_width) // 2,
            "left": 0,
            "right": width - target_width
        }
        x_offset = positions.get(position, positions["center"])

        # クロップしてエンコード
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", f"crop={target_width}:{height}:{x_offset}:0,scale=1080:1920",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "slow",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Short video creation failed: {result.stderr}")
            raise RuntimeError("Short video creation failed")

        logger.info(f"Short video created: {output_path}")
        return str(output_path)

    def add_intro_outro(self, video_path: str, output_path: str,
                       intro_path: Optional[str] = None,
                       outro_path: Optional[str] = None) -> str:
        """
        イントロ・アウトロを追加

        Args:
            video_path: 入力動画
            output_path: 出力パス
            intro_path: イントロ動画（オプション）
            outro_path: アウトロ動画（オプション）
        """
        logger.info("Adding intro/outro")

        # 結合するファイルのリスト
        files_to_concat = []

        if intro_path and Path(intro_path).exists():
            files_to_concat.append(intro_path)

        files_to_concat.append(video_path)

        if outro_path and Path(outro_path).exists():
            files_to_concat.append(outro_path)

        if len(files_to_concat) == 1:
            # イントロ/アウトロがない場合はコピーのみ
            shutil.copy(video_path, output_path)
            return str(output_path)

        # concat用リスト作成
        concat_file = Path(output_path).parent / "intro_outro_list.txt"

        with open(concat_file, "w", encoding="utf-8") as f:
            for file_path in files_to_concat:
                abs_path = Path(file_path).absolute()
                f.write(f"file '{abs_path}'\n")

        try:
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Intro/outro addition failed: {result.stderr}")
                raise RuntimeError("Intro/outro addition failed")

        finally:
            if concat_file.exists():
                concat_file.unlink()

        logger.info(f"Intro/outro added: {output_path}")
        return str(output_path)

    def create_instagram_reel(self, input_path: str, output_path: str) -> str:
        """
        Instagram Reel用に最適化（9:16, 60秒以内）

        Args:
            input_path: 入力動画
            output_path: 出力パス
        """
        logger.info("Creating Instagram Reel")

        # 1080x1920にスケール、60秒にトリム
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-t", "60",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Instagram Reel creation failed: {result.stderr}")
            raise RuntimeError("Instagram Reel creation failed")

        logger.info(f"Instagram Reel created: {output_path}")
        return str(output_path)

    def create_tiktok_video(self, input_path: str, output_path: str) -> str:
        """
        TikTok用に最適化（9:16, 高圧縮）

        Args:
            input_path: 入力動画
            output_path: 出力パス
        """
        logger.info("Creating TikTok video")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-crf", "28",  # TikTokは圧縮が強い
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"TikTok video creation failed: {result.stderr}")
            raise RuntimeError("TikTok video creation failed")

        logger.info(f"TikTok video created: {output_path}")
        return str(output_path)

    def _apply_vignette_pil(self, img: Image.Image, intensity: float = 0.3) -> Image.Image:
        """PILでビネット効果を適用"""
        width, height = img.size

        # グラデーションマスク作成
        mask = Image.new('L', (width, height), 0)
        draw = ImageDraw.Draw(mask)

        # 楕円形のグラデーション
        for i in range(min(width, height) // 2):
            alpha = int(255 * (i / (min(width, height) // 2)))
            bbox = [
                i, i,
                width - i, height - i
            ]
            draw.ellipse(bbox, fill=alpha)

        # マスクを適用
        mask = mask.filter(ImageFilter.GaussianBlur(radius=width // 10))

        # 元画像と合成
        vignette = Image.new('RGB', (width, height), (0, 0, 0))
        img = Image.composite(img, vignette, mask)

        return img
