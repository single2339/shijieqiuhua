"""WebSocket connection manager — per-run broadcast to connected clients.

Ported from intel-verify, adapted for osint-network's agent lifecycle.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[channel].append(ws)
        log.debug("WebSocket connected to channel %r (total: %d)", channel, len(self._connections[channel]))

    def disconnect(self, channel: str, ws: WebSocket) -> None:
        if channel in self._connections:
            try:
                self._connections[channel].remove(ws)
            except ValueError:
                pass
            log.debug("WebSocket disconnected from channel %r", channel)

    async def broadcast(self, channel: str, event_type: str, data: dict[str, Any] | None = None) -> None:
        message = json.dumps({
            "event_type": event_type,
            "data": data or {},
        }, ensure_ascii=False, default=str)

        dead: list[WebSocket] = []
        for ws in self._connections.get(channel, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(channel, ws)


ws_manager = ConnectionManager()
