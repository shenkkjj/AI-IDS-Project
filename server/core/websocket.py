import asyncio
from typing import Any

from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            user_connections = self.active_connections.setdefault(user_id, set())
            user_connections.add(websocket)
            total = sum(len(items) for items in self.active_connections.values())
        logger.info("WebSocket connected. user_id={} total={}", user_id, total)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            user_connections = self.active_connections.get(user_id)
            if user_connections is not None:
                user_connections.discard(websocket)
                if not user_connections:
                    self.active_connections.pop(user_id, None)
            total = sum(len(items) for items in self.active_connections.values())
        logger.info("WebSocket disconnected. user_id={} total={}", user_id, total)

    async def snapshot_connections(self, user_id: int) -> list[WebSocket]:
        async with self._lock:
            return list(self.active_connections.get(user_id, set()))

    async def broadcast_json(self, user_id: int, message: dict[str, Any]) -> None:
        targets = await self.snapshot_connections(user_id)
        if not targets:
            return

        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                user_connections = self.active_connections.get(user_id)
                if user_connections is not None:
                    for websocket in stale:
                        user_connections.discard(websocket)
                    if not user_connections:
                        self.active_connections.pop(user_id, None)


manager = ConnectionManager()
