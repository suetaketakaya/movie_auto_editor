"""Celery implementation of TaskQueuePort."""

from __future__ import annotations

import logging
from typing import Any

from celery import Celery
from celery.result import AsyncResult

logger = logging.getLogger(__name__)


class CeleryTaskQueue:
    """Implements :class:`TaskQueuePort` using Celery as the distributed task queue.

    Tasks are dispatched with ``send_task`` so that the caller does not need to
    import the concrete task modules.
    """

    def __init__(self, app: Celery | None = None, broker_url: str = "") -> None:
        if app is not None:
            self._app = app
        else:
            self._app = Celery(broker=broker_url or "redis://localhost:6379/0")
        logger.info("CeleryTaskQueue initialised (broker=%s)", self._app.conf.broker_url)

    # -- TaskQueuePort implementation ------------------------------------------

    def enqueue(self, task_name: str, args: dict) -> str:
        """Submit a task to the Celery broker and return the task id."""
        result: AsyncResult = self._app.send_task(task_name, kwargs=args)
        logger.info("Enqueued task %s -> %s", task_name, result.id)
        return result.id

    def get_status(self, task_id: str) -> dict:
        """Query the current state of a Celery task."""
        result = AsyncResult(task_id, app=self._app)
        info: Any = result.info

        response: dict[str, Any] = {
            "task_id": task_id,
            "status": result.status,
        }

        if isinstance(info, dict):
            response["result"] = info
        elif isinstance(info, Exception):
            response["error"] = str(info)
        elif result.ready():
            response["result"] = info

        return response

    def cancel(self, task_id: str) -> bool:
        """Attempt to revoke a Celery task."""
        try:
            self._app.control.revoke(task_id, terminate=True, signal="SIGTERM")
            logger.info("Cancelled task %s", task_id)
            return True
        except Exception:
            logger.exception("Failed to cancel task %s", task_id)
            return False
