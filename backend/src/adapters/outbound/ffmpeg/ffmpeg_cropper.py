"""
Smart cropping adapter wrapping legacy smart_cropper.py.
Uses OpenCV for face detection and FFmpeg for cropping.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess

import cv2

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import (
    FFMPEG_PATH,
    get_video_resolution,
    run_ffmpeg,
    run_ffprobe,
)

logger = logging.getLogger(__name__)


class FFmpegCropper:
    """Smart cropping: creates vertical (9:16) videos with tracking modes."""

    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    async def create_vertical_video(
        self, input_path: str, output_path: str, tracking_mode: str = "center"
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._create_vertical_sync, input_path, output_path, tracking_mode
        )

    def _create_vertical_sync(
        self, input_path: str, output_path: str, tracking_mode: str
    ) -> str:
        logger.info("Creating vertical video with %s tracking", tracking_mode)
        if tracking_mode == "face":
            return self._crop_with_face_tracking(input_path, output_path)
        elif tracking_mode == "action":
            return self._crop_with_action_tracking(input_path, output_path)
        return self._crop_center(input_path, output_path)

    def _crop_center(self, input_path: str, output_path: str) -> str:
        width, height = get_video_resolution(input_path)
        target_width = int(height * 9 / 16)
        x_offset = (width - target_width) // 2
        run_ffmpeg([
            "-i", input_path,
            "-vf", f"crop={target_width}:{height}:{x_offset}:0",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)

    def _crop_with_face_tracking(self, input_path: str, output_path: str) -> str:
        """Face-tracking crop (falls back to center if no faces detected)."""
        logger.info("Face tracking cropping")
        # Simplified: detect face in first frame, use as crop center
        cap = cv2.VideoCapture(input_path)
        try:
            ret, frame = cap.read()
            if ret:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
                if len(faces) > 0:
                    fx, fy, fw, fh = faces[0]
                    face_center_x = fx + fw // 2
                    width, height = get_video_resolution(input_path)
                    target_width = int(height * 9 / 16)
                    x_offset = max(0, min(width - target_width, face_center_x - target_width // 2))
                    run_ffmpeg([
                        "-i", input_path,
                        "-vf", f"crop={target_width}:{height}:{x_offset}:0",
                        "-c:a", "copy",
                        str(output_path),
                    ])
                    return str(output_path)
        finally:
            cap.release()
        return self._crop_center(input_path, output_path)

    def _crop_with_action_tracking(self, input_path: str, output_path: str) -> str:
        """Action-tracking crop (falls back to center)."""
        return self._crop_center(input_path, output_path)
