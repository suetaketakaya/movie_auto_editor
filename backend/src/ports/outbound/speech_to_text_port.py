"""Port for speech-to-text and subtitle generation."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class SpeechToTextPort(Protocol):
    def generate_subtitles(self, video_path: str, output_srt: str, language: str = "ja") -> str: ...
    def burn_subtitles(self, video_path: str, srt_path: str, output_path: str) -> str: ...
