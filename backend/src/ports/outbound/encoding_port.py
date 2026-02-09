"""Port for video encoding (GPU/CPU)."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class EncodingPort(Protocol):
    def encode_video(self, input_path: str, output_path: str, codec: str = "h264", quality: str = "high") -> str: ...
    def detect_gpu(self) -> str: ...
