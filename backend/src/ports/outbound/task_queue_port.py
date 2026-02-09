"""Port for task queue operations."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class TaskQueuePort(Protocol):
    def enqueue(self, task_name: str, args: dict) -> str: ...
    def get_status(self, task_id: str) -> dict: ...
    def cancel(self, task_id: str) -> bool: ...
