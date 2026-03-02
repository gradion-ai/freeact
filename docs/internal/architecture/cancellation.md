# Cancellation

Cooperative cancellation of a running agent turn, triggered by Escape in the terminal.

## Mechanism

- `Agent` owns an `asyncio.Event` (`_cancel_event`) checked at phase boundaries inside `stream()`.
- `Agent.cancel()` sets the event and calls `self._code_executor.cancel()` (kernel SIGINT + drain).
- The active `stream()` stops at the next boundary and yields a `Cancelled` event.
- No `CancelledError` propagation -- all cancellation is flag-based.

## Phase Boundaries

The cancel event is cleared at the start of each `stream()` call (main agent only, not subagents).

- **Between turns**: top of `while True` loop. Yields `Cancelled(phase="between_turns")`.
- **LLM streaming**: after each chunk. Breaks out; partial response preserved in history.
- **Post-LLM with tool calls**: synthetic `ToolReturnPart` for all emitted calls, then `Cancelled(phase="llm_streaming")`.
- **Approval wait**: `_await_approval_or_cancel()` races cancel against `approval.approved()`. Cancel auto-rejects.
- **Tool execution**: after each item in the `aiostream.merge()` loop. Synthetic returns for incomplete tools, then `Cancelled(phase="tool_execution")`.
- **Individual tool end**: `_execute_tool()` yields an interrupted return if cancelled (preserving partial output).

## Conversation Coherence

Orphaned tool calls get synthetic returns via `_interrupted_tool_return()`: `ToolReturnPart(content="Interrupted by user", metadata={"interrupted": True})`. This preserves the strict `[tool_use] -> [tool_result]` sequencing required by model APIs. Partial responses are kept in history, not discarded.

## Subagents

- Parent shares `_cancel_event` with the subagent.
- A monitor task in `_execute_subagent_task()` watches the event and calls `subagent._code_executor.cancel()`.
- Subagents do not clear the shared event.

## Terminal

- `TerminalApp` receives `cancel_fn` (bound to `Agent.cancel`) and tracks `_turn_in_progress`.
- Escape binding (`action_cancel_turn`): calls `cancel_fn()` and resolves any pending `_approval_future`.
- `check_action` guards the binding: only fires during an active turn.
- `ApprovalRequest.approve()` is idempotent to handle the race between cancel and terminal approval resolution.
