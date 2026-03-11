# Async Constraints

## Async generators for streaming

`Agent.stream()` is an `AsyncIterator[AgentEvent]`. Internal methods `_execute_tool()`, `_ipybox_execute_ipython_cell()`, and `_execute_subagent_task()` are also async generators that yield events.

Multiple concurrent tool executions from one model turn are merged via `aiostream.stream.merge()`.

## ResourceSupervisor for async lifecycle

`_ResourceSupervisor` (`freeact/agent/_supervisor.py`) wraps any async context manager in its own task, allowing concurrent start/stop via `asyncio.gather()`. Used for code executor and MCP servers.

Pattern: create supervisor, `await supervisor.start()`, later `await supervisor.stop()`.

## arun() for sync-in-async

Sync I/O operations are wrapped with `ipybox.utils.arun()` to run in an executor from async context:

- `Config.save()` wraps `_save_sync()`.
- `TerminalConfig.save()` wraps `_save_sync()`.
- `Config.load()` wraps JSON file read.

Exception: `SessionStore.load_messages()` is fully sync (reads file with `read_text()`). It is called via `arun()` from async callers. `SessionStore.append_messages()` is also sync (uses `open()` with `"a"` mode). This is intentional: session I/O is simple append/read and does not benefit from async file handles.

Contrast: `PermissionManager` uses `aiofiles` for its async `load()`/`save()` methods directly.

## Approval via Future

`ApprovalRequest` carries an `asyncio.Future[bool]`. The agent yields the request and awaits `approval.approved()`. The terminal calls `approval.approve(decision)` to resolve. `approve()` is idempotent (no-op if already resolved). Cancellation races against approval via `asyncio.wait(..., return_when=FIRST_COMPLETED)`.

## Concurrency control

- `asyncio.Semaphore` bounds concurrent subagents (`Agent._subagent_semaphore`).
- `asyncio.gather()` for concurrent supervisor start/stop.
- `aiostream.merge()` for concurrent tool execution streams.
