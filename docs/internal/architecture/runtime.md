# Runtime Architecture

This page documents agent runtime architecture only (`freeact/agent/*` plus the SDK surface in `freeact/events.py` and `freeact/toolcalls.py`).
It intentionally excludes CLI, terminal UI, and permission policy (the SDK is policy-free: it emits `ApprovalRequest`s, the embedder decides).

## Components

- `Agent` (`agent/agent.py`): public API (`start/stop`, async context manager, `stream(prompt, max_turns)`, `cancel()`, `session_id`, `tool_names`, `runtime`) and the turn loop. Constructed from a `ResolvedRuntime` (`config/resolve.py`); rejects `session_id` when persistence is disabled.
- `ApprovalGate` (`agent/approvals.py`): the single approval mechanism; creates and resolves all `ApprovalRequest`s, racing decision vs `CancelToken` vs `approval_timeout` into a typed `Decision`. See [constraints/async.md](constraints/async.md).
- `ToolExecutor` (`agent/executor.py`): routes each model tool call (code execution, `ipybox_reset`, `subagent_task`, MCP, unknown -> error return without approval) and owns the kernel bridge (ipybox executor with working dir reset, images dir, kernel env, sandbox settings; `execution_timeout` enforced by ipybox so approval wait time is excluded; one `asyncio.Lock` serializes kernel access). Runs one turn's calls concurrently via `aiostream.merge`. Intercepts in-kernel approvals: `!` shell commands (split per sub-command via `agent/shell.py`; rejecting any sub-command rejects the whole command), `%%bash` shell magic, and PTCs (`GenericCall` with `ptc=True`, name `<server>_<tool>`). Sets `approval_rejected` on the final `CodeExecutionOutput` instead of string matching.
- `MCPServerManager` (`agent/mcp.py`): server lifecycle (concurrent start/stop via `ResourceSupervisor`, partial-start cleanup), tool definition loading with server-name prefixes, per-server `exclude_tools`, call dispatch with exception-to-error-text conversion.
- `SubagentRunner` (`agent/subagents.py`): spawns child `Agent`s (`sub-` ids) from `runtime.for_subagent()`, bridges their events through a queue into the parent stream with `parent_corr_id` set, bounds concurrency with the `max_subagents` semaphore, propagates parent cancellation, converts child failure to an error `ToolOutput`. Default subagent `max_turns` is 100.
- `Session` (`agent/session.py`): single source of truth for message history; persistence and tool-result overflow per [constraints/persistence.md](constraints/persistence.md).
- Built-in tool definitions (ipybox tools, `subagent_task`) are JSON caches in `agent/tooldefs/`; regenerate manually against a live ipybox when its tool schemas change.

## Turn loop (`Agent._stream_turn`)

Append user request -> loop: stream model response (yield `ThoughtsChunk`/`ResponseChunk`, then `Thoughts`/`Response`), append the aggregated message; if no tool calls, the turn ends (no implicit turn limit). Otherwise run the executor, yielding `ApprovalRequest`/`CodeExecutionOutputChunk`/`CodeExecutionOutput`/`ToolOutput` events and collecting `ToolReturnPart`s plus media `UserPromptPart`s; append them as one `ModelRequest`. `max_turns` counts completed tool-execution rounds. Exceptions roll the turn's history back; cancellation does not (see [cancellation.md](cancellation.md)).

- Rejection ends the turn (INVARIANT): if any tool return has `metadata["rejected"]`, the agent yields a final `"Tool call rejected"` response and stops; nothing after the rejected action executes. Approval timeout counts as rejection; cancellation does not (it produces interrupted returns instead).
- Media flow: binary MCP results (e.g. `filesystem_read_media_file`) and a `"Read media: <path>"` tool return reach the model as a `UserPromptPart` with multimodal content appended alongside the tool returns.
- Every incomplete tool call gets a synthetic interrupted return so `[tool_use] -> [tool_result]` sequencing stays valid.

## Correlation ids

`ToolExecutor._execute` assigns a fresh `corr_id` per tool call; all events for that call (approval, chunks, outputs) carry it from construction (frozen events, no post-hoc mutation). Subagent events keep their own `corr_id` and get `parent_corr_id` set to the parent `subagent_task`'s corr_id via `dataclasses.replace` in `SubagentRunner`. Every event carries the originating `agent_id` (`main` or `sub-xxxx`).

## Lifecycle

`start()` loads persisted history, then starts executor and MCP servers concurrently (cleanup on partial failure); `stop()` stops both and collects errors into an `ExceptionGroup`. `Agent.stream` deterministically closes its turn stream on exit so abandonment propagates into tool execution and rejects pending approvals (see [constraints/async.md](constraints/async.md)).
