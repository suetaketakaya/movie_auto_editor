"""
Thumbnail A/B Testing Module
サムネイルA/Bテスト生成モジュール
"""

import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import subprocess
from typing import List

logger = logging.getLogger(__name__)
FFMPEG_PATH = "ffmpeg"


class ThumbnailABTester:
    """サムネイルA/Bテスター"""

    def __init__(self, config: dict):
        self.config = config
        self.thumbnail_config = config.get("thumbnail_ab_tester", {})

    def generate_multiple_variants(self, video_path: str, output_dir: str,
                                   title: str = "", kill_count: int = 0) -> List[str]:
        """
        複数のサムネイルバリエーションを生成

        Args:
            video_path: 動画パス
            output_dir: 出力ディレクトリ
            title: タイトルテキスト
            kill_count: キル数

        Returns:
            生成されたサムネイルパスのリスト
        """
        logger.info("Generating A/B test thumbnail variants")

        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        # ベストフレームを抽出
        base_frame = self._extract_best_frame(video_path, output_dir / "base_frame.png")

        variants = []

        # バリエーション1: シンプル (テキストのみ)
        variant1 = self._create_simple_variant(base_frame, output_dir / "variant1.png", title)
        variants.append(variant1)

        # バリエーション2: ボールド (大きなテキスト + 高コントラスト)
        variant2 = self._create_bold_variant(base_frame, output_dir / "variant2.png", title, kill_count)
        variants.append(variant2)

        # バリエーション3: ミニマル (小さなテキスト)
        variant3 = self._create_minimal_variant(base_frame, output_dir / "variant3.png", title)
        variants.append(variant3)

        # バリエーション4: ドラマティック (暗め + ハイライト)
        variant4 = self._create_dramatic_variant(base_frame, output_dir / "variant4.png", title)
        variants.append(variant4)

        # バリエーション5: ブライト (明るめ + 鮮やか)
        variant5 = self._create_bright_variant(base_frame, output_dir / "variant5.png", title, kill_count)
        variants.append(variant5)

        logger.info(f"Generated {len(variants)} thumbnail variants")
        return variants

    def _extract_best_frame(self, video_path: str, output_path: str) -> str:
        """ベストフレームを抽出 (中間地点)"""
        cmd = [
            FFMPEG_PATH, "-y", "-i", str(video_path),
            "-vf", "select='eq(pict_type\\,I)',scale=1280:720",
            "-frames:v", "1",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return str(output_path)

    def _create_simple_variant(self, base_frame: str, output_path: str, title: str) -> str:
        """シンプルバリエーション"""
        img = Image.open(base_frame)
        draw = ImageDraw.Draw(img)

        # テキスト描画
        font = ImageFont.truetype("arial.ttf", 60)
        text_bbox = draw.textbbox((0, 0), title, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x = (1280 - text_width) // 2
        y = 600

        # 影付きテキスト
        draw.text((x+3, y+3), title, fill=(0, 0, 0), font=font)
        draw.text((x, y), title, fill=(255, 255, 255), font=font)

        img.save(output_path)
        return str(output_path)

    def _create_bold_variant(self, base_frame: str, output_path: str, title: str, kill_count: int) -> str:
        """ボールドバリエーション"""
        img = Image.open(base_frame)

        # コントラスト強化
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)

        draw = ImageDraw.Draw(img)

        # 大きなテキスト
        font = ImageFont.truetype("arialbd.ttf", 80)
        draw.text((100, 500), title, fill=(255, 255, 0), font=font, stroke_width=4, stroke_fill=(0, 0, 0))

        # キル数バッジ
        if kill_count > 0:
            badge_font = ImageFont.truetype("arialbd.ttf", 60)
            draw.text((1000, 100), f"{kill_count} KILLS", fill=(255, 0, 0), font=badge_font, stroke_width=3, stroke_fill=(0, 0, 0))

        img.save(output_path)
        return str(output_path)

    def _create_minimal_variant(self, base_frame: str, output_path: str, title: str) -> str:
        """ミニマルバリエーション"""
        img = Image.open(base_frame)
        draw = ImageDraw.Draw(img)

        font = ImageFont.truetype("arial.ttf", 40)
        draw.text((50, 650), title, fill=(255, 255, 255), font=font)

        img.save(output_path)
        return str(output_path)

    def _create_dramatic_variant(self, base_frame: str, output_path: str, title: str) -> str:
        """ドラマティックバリエーション"""
        img = Image.open(base_frame)

        # 暗くする
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.7)

        # ビネット効果
        draw = ImageDraw.Draw(img, 'RGBA')
        draw.rectangle([(0, 0), (1280, 720)], fill=(0, 0, 0, 80))

        # テキスト
        font = ImageFont.truetype("arial.ttf", 70)
        draw.text((640, 360), title, fill=(255, 255, 255), font=font, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))

        img.save(output_path)
        return str(output_path)

    def _create_bright_variant(self, base_frame: str, output_path: str, title: str, kill_count: int) -> str:
        """ブライトバリエーション"""
        img = Image.open(base_frame)

        # 明るく鮮やかに
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.2)
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.3)

        draw = ImageDraw.Draw(img)

        # カラフルなテキスト
        font = ImageFont.truetype("arialbd.ttf", 65)
        draw.text((640, 600), title, fill=(255, 100, 100), font=font, anchor="mm", stroke_width=3, stroke_fill=(255, 255, 255))

        img.save(output_path)
        return str(output_path)
