"""
WebSocket handler for real-time progress updates.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per project."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str) -> None:
        await websocket.accept()
        if project_id not in self._connections:
            self._connections[project_id] = []
        self._connections[project_id].append(websocket)
        logger.info("WebSocket connected for project %s", project_id)

    def disconnect(self, websocket: WebSocket, project_id: str) -> None:
        if project_id in self._connections:
            self._connections[project_id] = [
                ws for ws in self._connections[project_id] if ws != websocket
            ]
            if not self._connections[project_id]:
                del self._connections[project_id]
        logger.info("WebSocket disconnected for project %s", project_id)

    async def broadcast(self, project_id: str, message: dict) -> None:
        """Broadcast message to all connections for a project."""
        connections = self._connections.get(project_id, [])
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, project_id)

    async def send_progress(
        self, project_id: str, progress: float, stage: str
    ) -> None:
        await self.broadcast(project_id, {
            "type": "progress",
            "project_id": project_id,
            "progress": progress,
            "stage": stage,
        })

    async def send_completion(self, project_id: str, result: dict) -> None:
        await self.broadcast(project_id, {
            "type": "completed",
            "project_id": project_id,
            "result": result,
        })

    async def send_error(self, project_id: str, error: str) -> None:
        await self.broadcast(project_id, {
            "type": "error",
            "project_id": project_id,
            "error": error,
        })


# Singleton manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for project progress tracking."""
    await manager.connect(websocket, project_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or handle client messages if needed
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
