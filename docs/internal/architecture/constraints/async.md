# Async Constraints

## ApprovalGate semantics (`freeact/agent/approvals.py`)

`ApprovalGate` is the only code that creates and resolves `ApprovalRequest`s. `decide(request)` races the consumer's decision against the shared `CancelToken` and the configured timeout (`asyncio.wait(..., timeout, FIRST_COMPLETED)`), returning a typed `Decision` (APPROVED/REJECTED/CANCELLED/TIMED_OUT).

Invariants:

- Exactly-once resolution: `ApprovalRequest.approve()` is a no-op once the future is done; a request resolved by cancellation/timeout ignores later `approve()` calls and vice versa.
- In `decide()`'s `finally`, the request is resolved as rejected BEFORE the approval waiter task is reaped: cancelling a task that awaits the request's future would cancel the future itself, making later `approved()` calls raise instead of returning the decision. This `finally` also covers abandonment (unwinding via `GeneratorExit`), so no other waiter on the same request hangs.
- Abandonment: every `yield approval` site in `ToolExecutor` (top-level calls in `_execute`, shell / shell-magic / PTC interception in `_execute_code`) is wrapped in `except GeneratorExit:` that calls `gate.resolve_rejected(approval)` (and for in-kernel approvals also rejects the ipybox request) before re-raising. This is required because under `aiostream.merge` backpressure producers sit suspended AT the yield, so consumer close raises `GeneratorExit` exactly there.

## Deterministic generator close chain

`async for` does not close its iterator on early exit, so closes are explicit:

`Agent.stream()` `finally` -> `turn_stream.aclose()` -> `Agent._stream_turn` `finally` -> `execution.aclose()` (the `ToolExecutor.run` generator) -> `aiostream.merge` context exit -> `GeneratorExit` into each per-call `_execute` generator -> approval yield-site handlers. This chain is what makes the abandonment invariant hold; do not replace `aiostream.merge` without re-running the ported invariant tests (its close-propagation semantics are pinned).

## Concurrency control

- `aiostream.stream.merge()` runs one model turn's tool calls concurrently (`ToolExecutor.run`).
- `asyncio.Lock` (`ToolExecutor._kernel_lock`) serializes kernel access: code actions and `ipybox_reset` share one kernel.
- `asyncio.Semaphore` bounds concurrent subagents (`SubagentRunner._semaphore`, `max_subagents`).
- `asyncio.gather()` starts/stops executor and MCP servers concurrently; `ResourceSupervisor` (`freeact/agent/supervisor.py`) wraps each async context manager in its own task so start/stop can be gathered and partial start failure cleans up only what started.
- `CancelToken` (`freeact/agent/approvals.py`, kept there to keep the dependency graph acyclic) is a flag-based cooperative signal; no `CancelledError` propagation for turn cancellation (see [cancellation.md](../cancellation.md)).
- `SubagentRunner._stream_subagent` runs the child agent in its own task and bridges events through a queue, so the child's lifecycle survives consumer-side pauses.

## Sync I/O from async code

All file I/O is synchronous and wrapped when called from async code (no `aiofiles`):

- `ipybox.utils.arun()` for `SessionStore` methods (`Session.load/append/rollback/materialize`) and tooldefs loading.
- `asyncio.to_thread()` for `PermissionManager` calls in `cli.py` and `terminal/approvals.py` (`allow_always`).
- Known exceptions (sync calls without wrapping): startup wiring in `cli.run` (`config.resolve`, `Agent` construction which composes the system prompt from bundled files) runs before the UI loop; `PermissionManager.is_allowed` / `allow_session` are in-memory only.
