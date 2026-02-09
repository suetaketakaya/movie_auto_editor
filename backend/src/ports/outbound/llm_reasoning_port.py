"""Port for LLM-based reasoning and clip determination."""
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol, runtime_checkable
if TYPE_CHECKING:
    from backend.src.core.entities.analysis_result import FrameAnalysis
    from backend.src.core.entities.clip import Clip
    from backend.src.core.entities.content_type import ContentType
    from backend.src.core.entities.creative_direction import CreativeDirection


@runtime_checkable
class LLMReasoningPort(Protocol):
    async def determine_clips(self, analysis_results: list[FrameAnalysis]) -> list[Clip]: ...
    async def generate_creative_direction(self, content_type: ContentType, analysis_summary: dict) -> CreativeDirection: ...
