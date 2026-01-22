from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class InboundMessage:
    chat_id: int
    message_id: int
    text: str


class SessionQueue:
    def __init__(self, *, maxsize: int = 0) -> None:
        self._q: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=maxsize)

    async def put(self, msg: InboundMessage) -> None:
        await self._q.put(msg)

    async def get(self, *, timeout: float | None = None) -> InboundMessage:
        if timeout is None:
            return await self._q.get()
        return await asyncio.wait_for(self._q.get(), timeout=timeout)

    def task_done(self) -> None:
        self._q.task_done()

    def empty(self) -> bool:
        return self._q.empty()
