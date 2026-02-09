"""Port for AI vision analysis of video frames."""
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol, runtime_checkable
if TYPE_CHECKING:
    from backend.src.core.entities.analysis_result import FrameAnalysis


@runtime_checkable
class VisionAnalysisPort(Protocol):
    async def analyze_frame(self, frame_path: str) -> FrameAnalysis: ...
    async def analyze_frames_batch(self, paths: list[str], concurrency: int = 4) -> list[FrameAnalysis]: ...
    def test_connection(self) -> bool: ...
