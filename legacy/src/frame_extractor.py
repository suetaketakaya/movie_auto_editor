"""
Frame Extractor Module
OpenCVを使用して動画からフレームを抽出
"""

import cv2
import os
import logging
from pathlib import Path
from typing import List
import asyncio

logger = logging.getLogger(__name__)


class FrameExtractor:
    """動画からフレームを抽出するクラス"""

    def __init__(self, config: dict):
        self.config = config
        self.interval_seconds = config["frame_extraction"]["interval_seconds"]
        self.quality = config["frame_extraction"]["quality"]
        self.max_frames = config["frame_extraction"]["max_frames"]

    async def extract_frames(self, video_path: str, output_dir: Path) -> List[str]:
        """
        動画から指定間隔でフレームを抽出

        Args:
            video_path: 動画ファイルのパス
            output_dir: フレーム保存先ディレクトリ

        Returns:
            抽出されたフレーム画像のパスリスト
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_frames_sync, video_path, output_dir)

    def _extract_frames_sync(self, video_path: str, output_dir: Path) -> List[str]:
        """同期版のフレーム抽出"""
        logger.info(f"Starting frame extraction from: {video_path}")

        # 動画を開く
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        # 動画情報を取得
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        logger.info(f"Video info - FPS: {fps}, Total frames: {total_frames}, Duration: {duration:.2f}s")

        # フレーム間隔を計算
        frame_interval = int(fps * self.interval_seconds)

        extracted_frames = []
        frame_count = 0
        saved_count = 0

        try:
            while True:
                ret, frame = cap.read()

                if not ret:
                    break

                # 指定間隔でフレームを保存
                if frame_count % frame_interval == 0:
                    timestamp = frame_count / fps
                    frame_filename = f"frame_{saved_count:06d}_t{timestamp:.2f}s.jpg"
                    frame_path = output_dir / frame_filename

                    # JPEG品質を指定して保存
                    cv2.imwrite(
                        str(frame_path),
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, self.quality]
                    )

                    extracted_frames.append(str(frame_path))
                    saved_count += 1

                    logger.debug(f"Extracted frame {saved_count} at {timestamp:.2f}s")

                    # 最大フレーム数に達したら終了
                    if saved_count >= self.max_frames:
                        logger.warning(f"Reached max frames limit: {self.max_frames}")
                        break

                frame_count += 1

        finally:
            cap.release()

        logger.info(f"Frame extraction completed: {saved_count} frames extracted")

        return extracted_frames

    def get_video_info(self, video_path: str) -> dict:
        """動画の基本情報を取得"""
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0

            return {
                "fps": fps,
                "total_frames": total_frames,
                "width": width,
                "height": height,
                "duration": duration,
                "duration_formatted": f"{int(duration // 60)}:{int(duration % 60):02d}"
            }
        finally:
            cap.release()
