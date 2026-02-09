"""Inbound port for video processing."""
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol, runtime_checkable
if TYPE_CHECKING:
    from backend.src.application.dto.process_request import ProcessRequest
    from backend.src.application.dto.process_result import ProcessResult


@runtime_checkable
class ProcessVideoUseCase(Protocol):
    async def execute(self, request: ProcessRequest) -> ProcessResult: ...
