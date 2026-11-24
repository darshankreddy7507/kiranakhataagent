"""Lightweight in-process SSE event bus for real-time dashboard updates."""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, AsyncGenerator


class RealtimeBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        payload = json.dumps(
            {
                "event": event_type,
                "data": data or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        msg = f"data: {payload}\n\n"
        for q in list(self._subscribers):
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._safe_put, q, msg)
            else:
                self._safe_put(q, msg)

    @staticmethod
    def _safe_put(q: asyncio.Queue[str], msg: str) -> None:
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass

    async def subscribe(self) -> AsyncGenerator[str, None]:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=64)
        self._subscribers.add(q)
        try:
            yield 'data: {"event":"connected"}\n\n'
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self._subscribers.discard(q)


realtime_bus = RealtimeBus()
