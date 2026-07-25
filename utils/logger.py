"""Structured logger for Andre — pushes events to the dashboard event bus."""
from __future__ import annotations

import asyncio
import time
from typing import Any


class EventLogger:
    """Lightweight wrapper around the shared asyncio.Queue event bus.

    Every agent uses one of these to push structured events that are
    consumed by the dashboard WebSocket broadcaster.
    """

    def __init__(self, agent_id: str, event_bus: asyncio.Queue):
        self.agent_id = agent_id
        self.event_bus = event_bus

    async def emit(self, event_type: str, **payload: Any) -> None:
        event = {
            "agent": self.agent_id,
            "type": event_type,
            "ts": time.time(),
        }
        event.update(payload)
        await self.event_bus.put(event)

    async def text(self, content: str) -> None:
        await self.emit("text", content=content)

    async def thinking(self, content: str) -> None:
        await self.emit("thinking", content=content)

    async def tool_use(self, query: str, max_results: int = 5) -> None:
        await self.emit("tool_use", query=query, max_results=max_results)

    async def search_result(self, query: str, result_count: int, pages_fetched: int) -> None:
        await self.emit(
            "search_result",
            query=query,
            result_count=result_count,
            pages_fetched=pages_fetched,
        )

    async def info(self, content: str) -> None:
        await self.emit("info", content=content)

    async def error(self, content: str) -> None:
        await self.emit("error", content=content)

    async def agent_start(self) -> None:
        await self.emit("agent_start")

    async def agent_done(
        self,
        tokens_in: int,
        tokens_out: int,
        reasoning_tokens: int,
        searches: int,
        pages: int,
        errors: int,
    ) -> None:
        await self.emit(
            "agent_done",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            reasoning_tokens=reasoning_tokens,
            searches=searches,
            pages=pages,
            errors=errors,
        )

    async def output_ready(self, markdown: str) -> None:
        await self.emit("output_ready", markdown=markdown)
