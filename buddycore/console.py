from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import WebSocket
else:
    WebSocket = Any


class ConsoleHub:
    def __init__(self, max_lines: int = 500):
        self.max_lines = max_lines
        self.buffer: deque[dict[str, Any]] = deque(maxlen=max_lines)
        self.clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)
        for item in list(self.buffer):
            await websocket.send_json(item)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.clients.discard(websocket)

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        return list(self.buffer)[-limit:]

    def publish_sync(self, item: dict[str, Any]) -> None:
        if "timestamp" not in item:
            item["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.buffer.append(item)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._broadcast(item))

    async def publish(self, item: dict[str, Any]) -> None:
        if "timestamp" not in item:
            item["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.buffer.append(item)
        await self._broadcast(item)

    async def _broadcast(self, item: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        async with self._lock:
            clients = list(self.clients)
        for ws in clients:
            try:
                await ws.send_json(item)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self.clients.discard(ws)
