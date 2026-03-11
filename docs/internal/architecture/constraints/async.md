# Async Constraints

## Async generators for streaming

`Agent.stream()` is an `AsyncIterator[AgentEvent]`. Internal methods `_execute_tool()`, `_ipybox_execute_ipython_cell()`, and `_execute_subagent_task()` are also async generators that yield events.

Multiple concurrent tool executions from one model turn are merged via `aiostream.stream.merge()`.

## ResourceSupervisor for async lifecycle

`_ResourceSupervisor` (`freeact/agent/_supervisor.py`) wraps any async context manager in its own task, allowing concurrent start/stop via `asyncio.gather()`. Used for code executor and MCP servers.

Pattern: create supervisor, `await supervisor.start()`, later `await supervisor.stop()`.

## Sync-in-async patterns

All file I/O in the codebase is synchronous, run from async context via `ipybox.utils.arun()`. Two patterns exist:

1. **Config classes own `_save_sync` / `arun()` internally.** `PersistentConfig.save()` wraps `_save_sync()` via `arun()`. `PersistentConfig.load()` wraps JSON file read via `arun()`. Subclasses override `_save_sync` for domain logic. Callers use `await config.save()` / `await Config.load()`.

2. **`SessionStore` and `PermissionManager` expose sync methods, callers use `arun()`.** These classes have plain `def` methods (`load`, `save`, `init`, `allow_always`). Async callers wrap with `await arun(manager.init)` or `await arun(manager.allow_always, tool_call)`.

No `aiofiles` usage exists in the codebase.

## Approval via Future

`ApprovalRequest` carries an `asyncio.Future[bool]`. The agent yields the request and awaits `approval.approved()`. The terminal calls `approval.approve(decision)` to resolve. `approve()` is idempotent (no-op if already resolved). Cancellation races against approval via `asyncio.wait(..., return_when=FIRST_COMPLETED)`.

## Concurrency control

- `asyncio.Semaphore` bounds concurrent subagents (`Agent._subagent_semaphore`).
- `asyncio.gather()` for concurrent supervisor start/stop.
- `aiostream.merge()` for concurrent tool execution streams.
