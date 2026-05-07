import asyncio
from typing import Any

from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        if user_id <= 0:
            await websocket.close(code=4001, reason="Authentication required")
            logger.warning("WebSocket rejected: missing user_id")
            return
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

    async def _heartbeat_loop(self) -> None:
        HEARTBEAT_INTERVAL = 30
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            async with self._lock:
                all_stale: list[tuple[int, WebSocket]] = []
                for uid, connections in list(self.active_connections.items()):
                    for ws in list(connections):
                        try:
                            await ws.send_json({"type": "ping"})
                        except Exception:
                            all_stale.append((uid, ws))
                for uid, ws in all_stale:
                    user_connections = self.active_connections.get(uid)
                    if user_connections is not None:
                        user_connections.discard(ws)
                        if not user_connections:
                            self.active_connections.pop(uid, None)
                if all_stale:
                    logger.info("Heartbeat cleaned {} stale connections", len(all_stale))

    def start_heartbeat(self) -> None:
        asyncio.ensure_future(self._heartbeat_loop())


manager = ConnectionManager()
