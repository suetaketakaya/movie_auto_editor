"""WebSocket notification adapter implementing NotificationPort.

Uses a connection-manager pattern to broadcast messages to all connected
WebSocket clients for a given project.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketNotifier:
    """Implements :class:`NotificationPort` by pushing JSON messages over
    WebSocket connections.

    Connections are registered per *project_id* so that each client only
    receives events for the project it subscribed to.
    """

    def __init__(self) -> None:
        # project_id -> set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}

    # -- connection management -------------------------------------------------

    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        """Accept a new WebSocket and register it under *project_id*."""
        await websocket.accept()
        self._connections.setdefault(project_id, set()).add(websocket)
        logger.info(
            "WebSocket connected for project %s (total=%d)",
            project_id,
            len(self._connections[project_id]),
        )

    async def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket from the connection pool."""
        conns = self._connections.get(project_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[project_id]
        logger.info("WebSocket disconnected for project %s", project_id)

    # -- internal broadcast ----------------------------------------------------

    async def _broadcast(self, project_id: str, payload: dict[str, Any]) -> None:
        """Send *payload* as JSON to every connection for *project_id*."""
        conns = self._connections.get(project_id)
        if not conns:
            logger.debug("No listeners for project %s; skipping broadcast", project_id)
            return

        message = json.dumps(payload)
        stale: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                logger.warning(
                    "Failed to send to WebSocket for project %s; marking stale",
                    project_id,
                )
                stale.append(ws)

        for ws in stale:
            conns.discard(ws)
        if not conns:
            del self._connections[project_id]

    # -- NotificationPort implementation ---------------------------------------

    async def send_progress(
        self, project_id: str, stage: str, progress: int, message: str
    ) -> None:
        """Broadcast a progress update for a project."""
        await self._broadcast(
            project_id,
            {
                "type": "progress",
                "project_id": project_id,
                "stage": stage,
                "progress": progress,
                "message": message,
            },
        )

    async def send_completion(self, project_id: str, outputs: dict) -> None:
        """Broadcast a completion event for a project."""
        await self._broadcast(
            project_id,
            {
                "type": "completion",
                "project_id": project_id,
                "outputs": outputs,
            },
        )

    async def send_error(self, project_id: str, error: str) -> None:
        """Broadcast an error event for a project."""
        await self._broadcast(
            project_id,
            {
                "type": "error",
                "project_id": project_id,
                "error": error,
            },
        )
