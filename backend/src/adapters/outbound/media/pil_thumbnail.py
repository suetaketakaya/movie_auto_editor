"""PIL / FFmpeg thumbnail and social-video adapter.

Wraps the legacy ``src.thumbnail_generator.ThumbnailGenerator`` and
``src.thumbnail_ab_tester.ThumbnailABTester`` logic, implementing
:class:`ThumbnailPort` for the hexagonal architecture.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import (
    run_ffmpeg,
    run_ffprobe,
    get_video_resolution,
)

logger = logging.getLogger(__name__)

# Default YouTube thumbnail dimensions.
_YT_WIDTH = 1280
_YT_HEIGHT = 720

# Social platform presets (width, height, crf, preset, max_duration).
_PLATFORM_PRESETS: dict[str, dict[str, Any]] = {
    "youtube_shorts": {
        "width": 1080,
        "height": 1920,
        "crf": "18",
        "preset": "slow",
        "max_duration": None,
    },
    "instagram_reel": {
        "width": 1080,
        "height": 1920,
        "crf": "23",
        "preset": "fast",
        "max_duration": 60,
        "audio_bitrate": "128k",
        "sample_rate": "44100",
    },
    "tiktok": {
        "width": 1080,
        "height": 1920,
        "crf": "28",
        "preset": "veryfast",
        "max_duration": None,
        "audio_bitrate": "128k",
        "sample_rate": "44100",
    },
}


class PILThumbnailAdapter:
    """Thumbnail generation and social-video export adapter.

    Satisfies :class:`~backend.src.ports.outbound.thumbnail_port.ThumbnailPort`.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._thumb_cfg = config.get("thumbnail", {})

    # -- Port interface --------------------------------------------------------

    def extract_best_frame(
        self,
        video_path: str,
        timestamp: float,
        output_path: str,
    ) -> str:
        """Grab a single high-quality frame via FFmpeg."""
        logger.info("Extracting frame at %.2fs for thumbnail", timestamp)
        run_ffmpeg([
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            str(output_path),
        ])
        return str(output_path)

    def create_youtube_thumbnail(
        self,
        frame_path: str,
        output_path: str,
        title_text: str = "",
        kill_count: int = 0,
    ) -> str:
        """Create a 1280x720 YouTube thumbnail with optional text overlays."""
        logger.info("Creating YouTube thumbnail")

        img = Image.open(frame_path)
        img = img.resize((_YT_WIDTH, _YT_HEIGHT), Image.Resampling.LANCZOS)

        # Contrast + colour enhancement
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Color(img).enhance(1.2)

        # Vignette
        img = self._apply_vignette_pil(img)

        draw = ImageDraw.Draw(img)
        title_font, count_font = self._load_fonts()

        # Title text at the bottom
        if title_text:
            bbox = draw.textbbox((0, 0), title_text, font=title_font)
            tw = bbox[2] - bbox[0]
            x = (_YT_WIDTH - tw) // 2
            y = 600
            draw.text((x + 5, y + 5), title_text, fill=(0, 0, 0), font=title_font)
            draw.text((x, y), title_text, fill=(255, 255, 0), font=title_font)

        # Kill-count badge (top-right)
        if kill_count > 0:
            count_text = f"{kill_count} KILLS"
            cb = draw.textbbox((0, 0), count_text, font=count_font)
            cw = cb[2] - cb[0]
            x = _YT_WIDTH - cw - 50
            y = 50
            padding = 20
            draw.rectangle(
                [x - padding, y - padding, x + cw + padding, y + 100 + padding],
                fill=(0, 0, 0, 180),
            )
            draw.text((x + 3, y + 3), count_text, fill=(0, 0, 0), font=count_font)
            draw.text((x, y), count_text, fill=(255, 50, 50), font=count_font)

        img.save(output_path, quality=95)
        logger.info("YouTube thumbnail created: %s", output_path)
        return str(output_path)

    def generate_ab_variants(
        self,
        video_path: str,
        output_dir: str,
        title: str = "",
        kill_count: int = 0,
    ) -> list[str]:
        """Generate multiple thumbnail A/B-test variants."""
        logger.info("Generating A/B test thumbnail variants")
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        base_frame = str(out / "base_frame.png")
        self._extract_keyframe(video_path, base_frame)

        variants: list[str] = []
        variant_creators = [
            ("variant_simple.jpg", self._variant_simple),
            ("variant_bold.jpg", self._variant_bold),
            ("variant_minimal.jpg", self._variant_minimal),
            ("variant_dramatic.jpg", self._variant_dramatic),
            ("variant_bright.jpg", self._variant_bright),
        ]

        for filename, creator in variant_creators:
            path = str(out / filename)
            creator(base_frame, path, title, kill_count)
            variants.append(path)

        logger.info("Generated %d thumbnail variants", len(variants))
        return variants

    async def generate_thumbnail(
        self,
        video_path: str,
        timestamp: float,
        output_path: str,
        style: str = "youtube",
    ) -> str:
        """High-level: extract a frame and build a styled thumbnail."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._generate_thumbnail_sync,
            video_path,
            timestamp,
            output_path,
            style,
        )

    async def create_social_video(
        self,
        input_path: str,
        output_path: str,
        platform: str = "youtube_shorts",
    ) -> str:
        """Create a platform-optimised social video (9:16 etc.)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._create_social_video_sync, input_path, output_path, platform
        )

    # -- Private helpers -------------------------------------------------------

    def _generate_thumbnail_sync(
        self,
        video_path: str,
        timestamp: float,
        output_path: str,
        style: str,
    ) -> str:
        frame_path = str(Path(output_path).with_suffix(".frame.jpg"))
        self.extract_best_frame(video_path, timestamp, frame_path)

        if style == "youtube":
            return self.create_youtube_thumbnail(frame_path, output_path)

        # Default: just return the extracted frame as the thumbnail.
        Path(frame_path).rename(output_path)
        return str(output_path)

    def _create_social_video_sync(
        self,
        input_path: str,
        output_path: str,
        platform: str,
    ) -> str:
        preset = _PLATFORM_PRESETS.get(platform)
        if preset is None:
            raise ValueError(f"Unknown platform: {platform!r}")

        logger.info("Creating social video for platform: %s", platform)

        w, h = preset["width"], preset["height"]
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        )

        args: list[str] = ["-i", input_path]

        if preset.get("max_duration") is not None:
            args.extend(["-t", str(preset["max_duration"])])

        args.extend([
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", str(preset["crf"]),
            "-preset", preset["preset"],
            "-c:a", "aac",
            "-b:a", preset.get("audio_bitrate", "192k"),
        ])

        if preset.get("sample_rate"):
            args.extend(["-ar", preset["sample_rate"]])

        args.append(str(output_path))
        run_ffmpeg(args)

        logger.info("Social video created: %s", output_path)
        return str(output_path)

    # -- A/B variant helpers ---------------------------------------------------

    def _extract_keyframe(self, video_path: str, output_path: str) -> str:
        """Extract a representative I-frame scaled to 1280x720."""
        run_ffmpeg([
            "-i", str(video_path),
            "-vf", r"select='eq(pict_type\,I)',scale=1280:720",
            "-frames:v", "1",
            str(output_path),
        ])
        return output_path

    def _variant_simple(
        self, base: str, out: str, title: str, _kill_count: int
    ) -> None:
        img = Image.open(base)
        draw = ImageDraw.Draw(img)
        font = self._safe_font("arial.ttf", 60)
        if title:
            bbox = draw.textbbox((0, 0), title, font=font)
            x = (_YT_WIDTH - (bbox[2] - bbox[0])) // 2
            draw.text((x + 3, 603), title, fill=(0, 0, 0), font=font)
            draw.text((x, 600), title, fill=(255, 255, 255), font=font)
        img.save(out, quality=95)

    def _variant_bold(
        self, base: str, out: str, title: str, kill_count: int
    ) -> None:
        img = ImageEnhance.Contrast(Image.open(base)).enhance(1.3)
        draw = ImageDraw.Draw(img)
        font = self._safe_font("arialbd.ttf", 80)
        if title:
            draw.text(
                (100, 500), title, fill=(255, 255, 0), font=font,
                stroke_width=4, stroke_fill=(0, 0, 0),
            )
        if kill_count > 0:
            badge = self._safe_font("arialbd.ttf", 60)
            draw.text(
                (1000, 100), f"{kill_count} KILLS", fill=(255, 0, 0),
                font=badge, stroke_width=3, stroke_fill=(0, 0, 0),
            )
        img.save(out, quality=95)

    def _variant_minimal(
        self, base: str, out: str, title: str, _kill_count: int
    ) -> None:
        img = Image.open(base)
        draw = ImageDraw.Draw(img)
        font = self._safe_font("arial.ttf", 40)
        if title:
            draw.text((50, 650), title, fill=(255, 255, 255), font=font)
        img.save(out, quality=95)

    def _variant_dramatic(
        self, base: str, out: str, title: str, _kill_count: int
    ) -> None:
        img = ImageEnhance.Brightness(Image.open(base)).enhance(0.7)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle([(0, 0), (_YT_WIDTH, _YT_HEIGHT)], fill=(0, 0, 0, 80))
        font = self._safe_font("arial.ttf", 70)
        if title:
            draw.text(
                (640, 360), title, fill=(255, 255, 255), font=font,
                anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0),
            )
        img.save(out, quality=95)

    def _variant_bright(
        self, base: str, out: str, title: str, _kill_count: int
    ) -> None:
        img = ImageEnhance.Brightness(Image.open(base)).enhance(1.2)
        img = ImageEnhance.Color(img).enhance(1.3)
        draw = ImageDraw.Draw(img)
        font = self._safe_font("arialbd.ttf", 65)
        if title:
            draw.text(
                (640, 600), title, fill=(255, 100, 100), font=font,
                anchor="mm", stroke_width=3, stroke_fill=(255, 255, 255),
            )
        img.save(out, quality=95)

    # -- Shared utilities ------------------------------------------------------

    @staticmethod
    def _safe_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            # Fall back to Windows system path
            try:
                return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
            except OSError:
                return ImageFont.load_default()

    @staticmethod
    def _load_fonts() -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, ...]:
        def _try(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
            for path in (name, f"C:/Windows/Fonts/{name}"):
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
            return ImageFont.load_default()

        return _try("impact.ttf", 80), _try("impact.ttf", 120)

    @staticmethod
    def _apply_vignette_pil(
        img: Image.Image,
        intensity: float = 0.3,
    ) -> Image.Image:
        """Apply an elliptical vignette using a gradient mask."""
        width, height = img.size

        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)

        half = min(width, height) // 2
        for i in range(half):
            alpha = int(255 * (i / half))
            draw.ellipse([i, i, width - i, height - i], fill=alpha)

        mask = mask.filter(ImageFilter.GaussianBlur(radius=width // 10))

        vignette = Image.new("RGB", (width, height), (0, 0, 0))
        return Image.composite(img, vignette, mask)
