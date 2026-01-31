"""
Automatic Subtitle Generation Module (Whisper)
自動字幕生成モジュール
"""

import logging
import subprocess
from pathlib import Path
import whisper
import json

logger = logging.getLogger(__name__)
FFMPEG_PATH = "ffmpeg"


class SubtitleGenerator:
    """自動字幕生成クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.subtitle_config = config.get("subtitle_generator", {})
        self.model = None

    def load_model(self):
        """Whisperモデルをロード"""
        if self.model is None:
            model_name = self.subtitle_config.get("model", "base")
            logger.info(f"Loading Whisper model: {model_name}")
            self.model = whisper.load_model(model_name)

    def generate_subtitles(self, video_path: str, output_srt: str,
                          language: str = "ja") -> str:
        """
        動画から自動字幕生成

        Args:
            video_path: 動画パス
            output_srt: 出力SRTファイルパス
            language: 言語コード

        Returns:
            SRTファイルパス
        """
        logger.info(f"Generating subtitles for: {video_path}")

        self.load_model()

        # 音声抽出
        audio_path = Path("temp_audio.wav")
        extract_cmd = [
            FFMPEG_PATH, "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(audio_path)
        ]
        subprocess.run(extract_cmd, check=True, capture_output=True)

        try:
            # Whisperで文字起こし
            result = self.model.transcribe(
                str(audio_path),
                language=language,
                task="transcribe",
                verbose=False
            )

            # SRT形式で保存
            self._write_srt(result["segments"], output_srt)

            logger.info(f"Subtitles generated: {output_srt}")
            return str(output_srt)

        finally:
            if audio_path.exists():
                audio_path.unlink()

    def _write_srt(self, segments, output_path: str):
        """SRT形式でファイルに書き込み"""
        with open(output_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                start = self._format_timestamp(segment["start"])
                end = self._format_timestamp(segment["end"])
                text = segment["text"].strip()

                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")

    def _format_timestamp(self, seconds: float) -> str:
        """秒をSRT形式のタイムスタンプに変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def burn_subtitles(self, video_path: str, srt_path: str, output_path: str) -> str:
        """字幕を動画に焼き込み"""
        logger.info("Burning subtitles into video")

        cmd = [
            FFMPEG_PATH, "-y", "-i", str(video_path),
            "-vf", f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BorderStyle=3'",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return str(output_path)
