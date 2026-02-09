"""Port for real-time notification delivery."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class NotificationPort(Protocol):
    async def send_progress(self, project_id: str, stage: str, progress: int, message: str) -> None: ...
    async def send_completion(self, project_id: str, outputs: dict) -> None: ...
    async def send_error(self, project_id: str, error: str) -> None: ...
