"""In-process implementation of TaskQueuePort for backward compatibility.

Runs tasks directly using ``asyncio.create_task`` so that no external broker
(Redis / RabbitMQ) is required.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class InProcessTaskQueue:
    """Implements :class:`TaskQueuePort` by executing tasks in the current
    event loop via :func:`asyncio.create_task`.

    Task functions must be registered with :meth:`register` before they can be
    enqueued.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._async_tasks: dict[str, asyncio.Task[Any]] = {}

    # -- registration ----------------------------------------------------------

    def register(
        self, task_name: str, fn: Callable[..., Coroutine[Any, Any, Any]]
    ) -> None:
        """Register an async callable under *task_name*."""
        self._registry[task_name] = fn
        logger.debug("Registered in-process task: %s", task_name)

    # -- TaskQueuePort implementation ------------------------------------------

    def enqueue(self, task_name: str, args: dict) -> str:
        """Schedule a registered task in the running event loop."""
        fn = self._registry.get(task_name)
        if fn is None:
            raise ValueError(
                f"Task '{task_name}' is not registered. "
                f"Available: {list(self._registry)}"
            )

        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "task_id": task_id,
            "task_name": task_name,
            "status": "PENDING",
            "result": None,
            "error": None,
        }

        async def _wrapper() -> None:
            self._tasks[task_id]["status"] = "STARTED"
            try:
                result = await fn(**args)
                self._tasks[task_id]["status"] = "SUCCESS"
                self._tasks[task_id]["result"] = result
            except asyncio.CancelledError:
                self._tasks[task_id]["status"] = "REVOKED"
                logger.info("Task %s was cancelled", task_id)
            except Exception as exc:
                self._tasks[task_id]["status"] = "FAILURE"
                self._tasks[task_id]["error"] = str(exc)
                logger.exception("Task %s failed", task_id)

        try:
            loop = asyncio.get_running_loop()
            async_task = loop.create_task(_wrapper(), name=f"task-{task_id}")
        except RuntimeError:
            # No running loop – unlikely in an async application, but guard anyway.
            raise RuntimeError(
                "InProcessTaskQueue.enqueue requires a running asyncio event loop"
            )

        self._async_tasks[task_id] = async_task
        logger.info("Enqueued in-process task %s -> %s", task_name, task_id)
        return task_id

    def get_status(self, task_id: str) -> dict:
        """Return the current status of an in-process task."""
        info = self._tasks.get(task_id)
        if info is None:
            return {"task_id": task_id, "status": "UNKNOWN"}
        return dict(info)

    def cancel(self, task_id: str) -> bool:
        """Cancel a running in-process task."""
        async_task = self._async_tasks.get(task_id)
        if async_task is None:
            logger.warning("Cannot cancel unknown task %s", task_id)
            return False
        if async_task.done():
            logger.debug("Task %s already finished", task_id)
            return False
        async_task.cancel()
        logger.info("Cancelled in-process task %s", task_id)
        return True
