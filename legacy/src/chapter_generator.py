"""
Automatic Chapter Generation Module
自動チャプター生成モジュール (YouTube対応)
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ChapterGenerator:
    """自動チャプター生成クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.chapter_config = config.get("chapter_generator", {})

    def generate_chapters(self, clips: List[Dict], multi_kills: List[Dict] = None) -> List[Dict]:
        """
        クリップからチャプターを自動生成

        Args:
            clips: クリップリスト
            multi_kills: マルチキル情報

        Returns:
            チャプターリスト [{timestamp, title}, ...]
        """
        logger.info("Generating automatic chapters")

        chapters = []
        current_time = 0.0

        # イントロチャプター
        chapters.append({
            "timestamp": "0:00",
            "title": "🎮 Intro"
        })

        # クリップごとにチャプター生成
        for i, clip in enumerate(clips, 1):
            timestamp = self._format_timestamp(current_time)

            # マルチキルチェック
            chapter_title = f"Clip {i}"
            if multi_kills:
                for mk in multi_kills:
                    if clip["start"] <= mk["timestamp"] <= clip["end"]:
                        chapter_title = f"🔥 {mk['type']}"
                        break

            chapters.append({
                "timestamp": timestamp,
                "title": chapter_title
            })

            current_time += (clip["end"] - clip["start"])

        logger.info(f"Generated {len(chapters)} chapters")
        return chapters

    def _format_timestamp(self, seconds: float) -> str:
        """秒をYouTubeチャプター形式に変換"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def export_youtube_description(self, chapters: List[Dict], output_file: str):
        """YouTube説明文用のチャプターをエクスポート"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("📖 Chapters:\n")
            for chapter in chapters:
                f.write(f"{chapter['timestamp']} - {chapter['title']}\n")

        logger.info(f"Chapter description exported: {output_file}")
