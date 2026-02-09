"""Port for text overlay operations."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class TextOverlayPort(Protocol):
    def add_kill_counter(self, input_path: str, output_path: str, kill_timestamps: list[float]) -> str: ...
    def add_text_popup(self, input_path: str, output_path: str, text: str, timestamp: float, duration: float = 2.0, position: str = "center") -> str: ...
    def add_subtitle(self, input_path: str, output_path: str, subtitle_file: str) -> str: ...
