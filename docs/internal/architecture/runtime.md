# Runtime Architecture

This page documents agent runtime architecture only (`freeact/agent/*`).
It intentionally excludes CLI, terminal UI, and longer-lived permission policy layers.

## Core Agent

- `freeact/agent/events.py` defines all typed stream events (`ResponseChunk`, `Response`, `Thoughts*`, `ApprovalRequest`, `CodeExecutionOutput*`, `ToolOutput`).
- `freeact/agent/core.py` contains the `Agent` class and main orchestration loop.
- `freeact/agent/_supervisor.py` contains `_ResourceSupervisor`, a generic async lifecycle utility for context managers.
- `freeact/agent/_subagent.py` contains `_SubagentRunner`, which bridges subagent events via a queue.
- `_execute_tool()` handles approval, `_dispatch_tool()` routes to the appropriate handler.
- Multiple tool calls from one model turn execute concurrently via `aiostream.merge`.

## Subagents

- Subagents are invoked through `subagent_task`.
- `_execute_subagent_task()` creates a nested `Agent` with `enable_subagents=False`.
- Parent and subagent events share one stream and are separated by `agent_id`.
- Concurrent subagents are bounded by `max_subagents` via `asyncio.Semaphore`.

## Configuration

- `freeact/agent/config/` handles `.freeact/` initialization and loading.
- `Config()` creates defaults in memory; `save()` persists static config artifacts; `load()` reads persisted config when present.

## Tools

- Bundled tool-definition caches:
  - ipybox tools: `freeact/tools/ipybox.json`
  - subagent tool: `freeact/tools/subagent.json`
- JSON MCP calls use `mcp_servers`.
- Programmatic tool calling uses generated Python APIs from `ptc_servers` in `.freeact/generated/mcptools/`.
- User-defined generated tools live in `.freeact/generated/gentools/`.

## Sessions

- Session persistence: `freeact/agent/store.py`.
- Main-session rehydration loads `main.jsonl`; subagent JSONL files are persisted for audit.
- Tool results above `Config.tool_result_inline_max_bytes` are stored in `.freeact/sessions/<session-id>/tool-results/<file-id>.<ext>` and replaced inline with a threshold/size notice plus preview lines.

## Approvals

- All tool executions require approval and surface as `ApprovalRequest` (including nested programmatic tool calls encountered during `ipybox_execute_ipython_cell`).
- Rejected approvals are reflected as rejected tool returns and end the current agent turn with a `"Tool call rejected"` response.
