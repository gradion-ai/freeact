# Cancellation

Cooperative cancellation of a running agent turn, triggered by Escape in the terminal.

## Mechanism

- `CancelToken` (`freeact/agent/approvals.py`) is shared across a turn's components (Agent, ApprovalGate, ToolExecutor, SubagentRunner) and checked at phase boundaries.
- `Agent.cancel()` sets the token and calls `ToolExecutor.cancel_kernel()` (ipybox kernel SIGINT + drain).
- The active `stream()` stops at the next boundary and yields `Cancelled(phase=...)` (`Phase` in `freeact/events.py`).
- No `CancelledError` propagation -- all turn cancellation is flag-based.
- `stream()` clears the token at the start of each call for the main agent only (subagent ids start with `sub-`; they share the parent's token and never clear it).

## Phase boundaries (`Agent._stream_turn`)

- **Between turns**: top of the loop. Yields `Cancelled(phase=BETWEEN_TURNS)`.
- **LLM streaming**: checked after each chunk; breaks out, the aggregated (partial) response is appended to history. If the partial response contains tool calls, synthetic returns are appended for all of them. Yields `Cancelled(phase=LLM_STREAMING)`.
- **Approval wait**: `ApprovalGate.decide()` races the token; result `Decision.CANCELLED` makes the executor yield an interrupted return for that call (not a rejected one, so cancellation does not trigger the rejection-ends-turn response).
- **Tool execution**: checked after each merged item; the execution stream is closed, every tool call without a return gets a synthetic return, the returns are appended, then `Cancelled(phase=TOOL_EXECUTION)`.
- **Individual tool end**: `ToolExecutor._execute` yields an interrupted return carrying any content produced so far (partial output preserved).

## Conversation coherence (INVARIANT)

After cancellation every tool call the model issued has a tool return in history: `interrupted_tool_return()` (`freeact/agent/executor.py`) produces `ToolReturnPart(content="Interrupted by user", metadata={"interrupted": True})`. This preserves the strict `[tool_use] -> [tool_result]` sequencing required by model APIs, so persisted history stays valid for resume. Cancellation NEVER rolls history back; `Session.rollback` is exclusively the turn-exception path.

## Subagents

- The parent's `CancelToken` is passed to each subagent's constructor.
- A monitor task in `SubagentRunner.run_task` watches the token and calls `subagent.cancel()`, which also interrupts the subagent's kernel.
- In-kernel approvals resolved as cancelled also reject the ipybox-side request so the kernel unblocks.

## Terminal

- `TerminalApp` receives `cancel` (bound to `Agent.cancel`) and tracks `_turn_in_progress`.
- Escape binding (`action_cancel_turn`): calls `cancel()` and `ApprovalController.reject_pending()` to resolve any pending approval-bar future; `check_action` only enables it during an active turn.
- `ApprovalRequest.approve()` is idempotent, handling the race between cancellation/timeout and a terminal decision.
