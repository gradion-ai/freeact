import asyncio
from typing import Any


class _ResourceSupervisor:
    """Keeps a single async context manager running in its own task.

    Unlike `AsyncExitStack`, multiple supervisors can be started and
    stopped concurrently via `asyncio.gather`. This also allows partial
    cleanup when concurrent start fails: successfully started resources
    are stopped while failed ones are no-ops.
    """

    def __init__(self, resource: Any, name: str):
        self._resource = resource
        self._name = name
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._entered_resource: Any | None = None
        self._error: Exception | None = None

    async def start(self) -> Any:
        """Start resource task and wait until context is entered."""
        if self._task is not None:
            raise RuntimeError(f"Resource supervisor for '{self._name}' already started")

        self._task = asyncio.create_task(self._run(), name=f"resource-{self._name}")
        await self._ready.wait()

        if self._error is not None:
            raise RuntimeError(f"Failed to start resource '{self._name}'") from self._error

        return self._entered_resource

    async def stop(self) -> None:
        """Signal resource task to exit context and wait for completion."""
        if self._task is None:
            return

        self._stop.set()
        await self._task

    async def _run(self) -> None:
        try:
            async with self._resource as entered_resource:
                self._entered_resource = entered_resource
                self._ready.set()
                await self._stop.wait()
        except Exception as e:
            self._error = e
            self._ready.set()
            raise
