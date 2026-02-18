from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, AsyncIterator

from freeact.agent.events import AgentEvent

if TYPE_CHECKING:
    from freeact.agent.core import Agent


class _SubagentRunner:
    """Runs a subagent in a dedicated task and streams its events safely."""

    def __init__(self, subagent: Agent, semaphore: asyncio.Semaphore):
        self._subagent = subagent
        self._semaphore = semaphore

    async def stream(self, prompt: str, max_turns: int) -> AsyncIterator[AgentEvent]:
        queue: asyncio.Queue[AgentEvent | Exception | None] = asyncio.Queue()

        async def run_subagent() -> None:
            try:
                async with self._semaphore:
                    async with self._subagent:
                        async for event in self._subagent.stream(prompt, max_turns=max_turns):
                            await queue.put(event)
            except Exception as e:
                queue.put_nowait(e)
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(run_subagent())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    return
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
