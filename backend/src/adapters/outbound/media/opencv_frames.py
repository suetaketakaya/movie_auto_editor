"""OpenCV-based frame extraction adapter.

Wraps the legacy ``src.frame_extractor.FrameExtractor`` logic and
implements :class:`FrameExtractionPort` for the hexagonal architecture.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import cv2

logger = logging.getLogger(__name__)

# Default configuration values used when keys are absent.
_DEFAULT_INTERVAL: float = 5.0
_DEFAULT_QUALITY: int = 85
_DEFAULT_MAX_FRAMES: int = 2000


class OpenCVFrameExtractor:
    """Extracts video frames using OpenCV.

    Satisfies :class:`~backend.src.ports.outbound.frame_extraction_port.FrameExtractionPort`.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        fe_cfg = config.get("frame_extraction", {})
        self._interval_seconds: float = fe_cfg.get("interval_seconds", _DEFAULT_INTERVAL)
        self._quality: int = fe_cfg.get("quality", _DEFAULT_QUALITY)
        self._max_frames: int = fe_cfg.get("max_frames", _DEFAULT_MAX_FRAMES)

    # -- Port interface --------------------------------------------------------

    async def extract_frames(
        self,
        video_path: str,
        output_dir: Path,
        interval_seconds: float = 2.0,
        max_frames: int = 2000,
    ) -> list[str]:
        """Extract frames at *interval_seconds* intervals.

        The method honours the caller-supplied ``interval_seconds`` and
        ``max_frames`` parameters, falling back to the instance defaults
        when the caller does not override them explicitly.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        effective_interval = interval_seconds if interval_seconds != 2.0 else self._interval_seconds
        effective_max = max_frames if max_frames != 2000 else self._max_frames

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._extract_frames_sync,
            video_path,
            out,
            effective_interval,
            effective_max,
        )

    async def extract_frame_at(
        self,
        video_path: str,
        timestamp: float,
        output_path: str,
    ) -> str:
        """Extract a single frame at an exact *timestamp* (seconds)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._extract_frame_at_sync, video_path, timestamp, output_path
        )

    def get_video_info(self, video_path: str) -> dict:
        """Return basic video metadata via OpenCV."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        try:
            fps: float = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0.0

            return {
                "fps": fps,
                "total_frames": total_frames,
                "width": width,
                "height": height,
                "duration": duration,
                "duration_formatted": f"{int(duration // 60)}:{int(duration % 60):02d}",
            }
        finally:
            cap.release()

    # -- Private sync helpers --------------------------------------------------

    def _extract_frames_sync(
        self,
        video_path: str,
        output_dir: Path,
        interval_seconds: float,
        max_frames: int,
    ) -> list[str]:
        logger.info("Starting frame extraction from: %s (interval=%.2fs)", video_path, interval_seconds)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        fps: float = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0.0
        logger.info(
            "Video info - FPS: %.2f, Total frames: %d, Duration: %.2fs",
            fps, total_frames, duration,
        )

        frame_interval = max(1, int(fps * interval_seconds))
        extracted: list[str] = []
        frame_count = 0
        saved_count = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % frame_interval == 0:
                    timestamp = frame_count / fps
                    frame_filename = f"frame_{saved_count:06d}_t{timestamp:.2f}s.jpg"
                    frame_path = output_dir / frame_filename

                    cv2.imwrite(
                        str(frame_path),
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, self._quality],
                    )
                    extracted.append(str(frame_path))
                    saved_count += 1
                    logger.debug("Extracted frame %d at %.2fs", saved_count, timestamp)

                    if saved_count >= max_frames:
                        logger.warning("Reached max frames limit: %d", max_frames)
                        break

                frame_count += 1
        finally:
            cap.release()

        logger.info("Frame extraction completed: %d frames extracted", saved_count)
        return extracted

    def _extract_frame_at_sync(
        self,
        video_path: str,
        timestamp: float,
        output_path: str,
    ) -> str:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        try:
            fps: float = cap.get(cv2.CAP_PROP_FPS)
            target_frame = int(timestamp * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

            ret, frame = cap.read()
            if not ret:
                raise RuntimeError(
                    f"Failed to read frame at timestamp {timestamp:.2f}s "
                    f"(frame {target_frame})"
                )

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(
                str(output_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._quality],
            )
            logger.info("Extracted single frame at %.2fs -> %s", timestamp, output_path)
            return str(output_path)
        finally:
            cap.release()
