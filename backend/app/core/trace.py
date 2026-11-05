"""Live trace bus. Modules emit events; the UI streams them per thread over SSE."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class TraceBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, thread_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[thread_id].append(q)
        return q

    def unsubscribe(self, thread_id: str, q: asyncio.Queue) -> None:
        if q in self._subs.get(thread_id, []):
            self._subs[thread_id].remove(q)

    async def emit(self, thread_id: str, case_id: str | None, layer: str, actor: str,
                   event: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """layer: router | case_manager | department | submodule | always_on | service"""
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "thread_id": thread_id,
            "case_id": case_id,
            "layer": layer,
            "actor": actor,
            "event": event,
            "data": data or {},
        }
        for q in self._subs.get(thread_id, []):
            await q.put(payload)
        return payload


bus = TraceBus()
