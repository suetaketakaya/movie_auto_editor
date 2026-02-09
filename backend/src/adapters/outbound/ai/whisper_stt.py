"""
Whisper speech-to-text adapter wrapping legacy subtitle_generator.py.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import FFMPEG_PATH, run_ffmpeg

logger = logging.getLogger(__name__)


class WhisperSTTAdapter:
    """Speech-to-text using OpenAI Whisper."""

    def __init__(self, model_name: str = "base"):
        self._model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            import whisper
            logger.info("Loading Whisper model: %s", self._model_name)
            self._model = whisper.load_model(self._model_name)

    async def transcribe(
        self, audio_path: str, language: str = "ja"
    ) -> list[dict]:
        """Transcribe audio file and return segments."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._transcribe_sync, audio_path, language
        )

    def _transcribe_sync(self, audio_path: str, language: str) -> list[dict]:
        self._load_model()
        result = self._model.transcribe(
            audio_path, language=language, task="transcribe", verbose=False
        )
        return [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ]

    async def generate_srt(
        self, video_path: str, output_srt: str, language: str = "ja"
    ) -> str:
        """Extract audio from video, transcribe, and write SRT file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._generate_srt_sync, video_path, output_srt, language
        )

    def _generate_srt_sync(
        self, video_path: str, output_srt: str, language: str
    ) -> str:
        logger.info("Generating subtitles for: %s", video_path)
        audio_path = Path(video_path).parent / "temp_audio_whisper.wav"
        try:
            run_ffmpeg([
                "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(audio_path),
            ])
            segments = self._transcribe_sync(str(audio_path), language)
            self._write_srt(segments, output_srt)
            logger.info("Subtitles generated: %s", output_srt)
            return str(output_srt)
        finally:
            if audio_path.exists():
                audio_path.unlink()

    def _write_srt(self, segments: list[dict], output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                start = self._format_ts(seg["start"])
                end = self._format_ts(seg["end"])
                f.write(f"{i}\n{start} --> {end}\n{seg['text']}\n\n")

    @staticmethod
    def _format_ts(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    async def burn_subtitles(
        self, video_path: str, srt_path: str, output_path: str
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._burn_sync, video_path, srt_path, output_path
        )

    def _burn_sync(self, video_path: str, srt_path: str, output_path: str) -> str:
        logger.info("Burning subtitles into video")
        run_ffmpeg([
            "-i", str(video_path),
            "-vf", f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BorderStyle=3'",
            "-c:a", "copy",
            str(output_path),
        ])
        return str(output_path)
