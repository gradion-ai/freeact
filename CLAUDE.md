## Project Overview

Freeact is a lightweight, general-purpose agent that acts via [code actions](https://machinelearning.apple.com/research/codeact) rather than JSON tool calls. It writes executable Python code in a sandboxed IPython kernel ([ipybox](https://gradion-ai.github.io/ipybox/)), where variables persist across executions. Tools can be called programmatically (via generated Python APIs) or through JSON tool calls (via MCP servers).

Key dependencies: pydantic-ai (LLM orchestration), ipybox (sandboxed kernel execution), aiostream (parallel async streaming). Python >=3.11,<3.15.

## Development Commands

```bash
uv sync                      # Install dependencies
uv run invoke cc             # Run code checks (auto-fixes formatting, mypy errors need manual fix)
uv run invoke test           # Run all tests
uv run invoke ut             # Run unit tests only
uv run invoke it             # Run integration tests only
uv run invoke test --cov     # Run tests with coverage

# Parallel test execution (uses pytest-xdist)
uv run invoke it --parallel
uv run invoke test --parallel

# Single test file
uv run pytest -xsv tests/integration/test_agent.py

# Single test
uv run pytest -xsv tests/integration/test_agent.py::test_name

# Documentation
uv run invoke build-docs     # Build docs
uv run invoke serve-docs     # Serve docs at localhost:8000
```

**Note:** `invoke cc` only checks files under version control. Run `git add` on new files first.

**Note:** Integration tests are significantly faster with the `--parallel` option. All tests are isolated (each gets its own ipybox kernel on a random port) so parallel execution is safe.

## Architecture

### Agent Core (`freeact/agent/core.py`)

The `Agent` class is the central orchestration point. It uses pydantic-ai's `model_request_stream` for LLM interaction and ipybox's `CodeExecutor` for sandboxed Python execution. Key design:

- **Event streaming**: `Agent.stream()` is an async generator yielding `AgentEvent` subclasses (`ResponseChunk`, `Response`, `ThoughtsChunk`, `Thoughts`, `ApprovalRequest`, `CodeExecutionOutputChunk`, `CodeExecutionOutput`, `ToolOutput`).
- **Event base class**: All events inherit from `AgentEvent(kw_only=True)` with an `agent_id: str` field. The `kw_only=True` on the base class avoids field-ordering issues with subclass fields that lack defaults.
- **Tool dispatch**: `_execute_tool()` uses `match/case` on `tool_name` to route to ipybox execution, MCP tool calls, or subagent task spawning. All paths yield an `ApprovalRequest` before execution.
- **Agentic loop**: `stream()` loops model responses and tool executions until the model produces no tool calls or `max_turns` is reached.
- **Parallel tool execution**: Multiple tool calls from a single model response execute concurrently via `aiostream.merge(*tool_streams)`.

### Subagent System

Subagents are spawned via the `subagent_task` JSON tool call:

- `_execute_subagent_task()` creates a new `Agent` with `enable_subagents=False` (prevents nesting).
- Each subagent gets its own ipybox kernel, MCP server connections (via `mcp_servers`), and message history.
- `_SubagentRunner` wraps the subagent in a background task with a queue-based event bridge, enabling safe streaming from a separate task.
- Subagent events bubble transparently through the parent's stream. Events carry `agent_id` (prefixed `sub-`) to distinguish from parent events.
- The final `ToolOutput` carrying the subagent's last response uses the parent's `agent_id`.
- Concurrency is bounded by `asyncio.Semaphore(max_subagents)` (default 5).

### Configuration (`freeact/agent/config/`)

- `Config` class loads `.freeact/` directory (skills, system prompt, server configs). Raw MCP server configs (`mcp_servers`) are passed directly to agents, which create their own pydantic-ai `MCPServer` instances.
- `Config.init()` classmethod scaffolds `.freeact/` from bundled templates on first run, copying only files that don't already exist.

### Tool System

- **ipybox tools**: Tool definitions cached in `freeact/tools/ipybox.json` and `subagent.json`. Loaded via `load_ipybox_tool_definitions()` and `load_subagent_task_tool_definitions()`.
- **MCP servers** (`mcp-servers` in `config.json`): Called directly via JSON tool calls. Server connections managed by `_ResourceSupervisor` for lifecycle management.
- **PTC servers** (`ptc-servers` in `config.json`): Python APIs auto-generated to `.freeact/generated/mcptools/<server>/` at startup via `generate_mcp_sources()` in `freeact/tools/pytools/apigen.py`. Agent writes code importing these APIs. User-defined tools go in `.freeact/generated/gentools/`.
- **Tool search** (`freeact/tools/pytools/search/`): Two modes via `tool-search` in `config.json`. Basic (`search/basic.py`) provides `list_categories`/`list_tools` MCP tools. Hybrid (`search/hybrid/`) adds BM25 + vector search with SQLite storage.

### Session Persistence (`freeact/agent/store.py`)

`SessionStore` persists pydantic-ai message history as JSONL envelopes to `.freeact/sessions/<session-uuid>/<agent-id>.jsonl`. Each line is an envelope: `{"v": 1, "message": {...}, "meta": {"ts": "..."}}`.

- Messages are appended incrementally at three points: initial user request, aggregated model response, and tool return request.
- On resume (`--session-id <uuid>`), only `main.jsonl` is loaded into the agent's history. Subagent files are persisted for audit but not rehydrated.
- Corruption handling: malformed trailing line is ignored; malformed non-tail lines cause a load failure.

### Approval Flow

All tool executions require approval. `Agent.stream()` yields `ApprovalRequest` before executing any tool:

- **JSON tool calls**: `ApprovalRequest` yielded in `_execute_tool()` before execution.
- **PTC tool calls**: ipybox yields `ipybox.ApprovalRequest` which freeact wraps in its own `ApprovalRequest`.
- **Subagent approvals**: Bubble up through the parent's event stream transparently.
- `Terminal` uses `PermissionManager` for always/session/once approval modes, persisted to `.freeact/permissions.json`.

### Other Components

- `freeact/media/`: Prompt parsing (`parse_prompt()`) for `@file` references, image loading/downscaling.
- `freeact/terminal/interface.py`: `Terminal` class handles conversation loop, event rendering, approval handling.
- `freeact/permissions.py`: `PermissionManager` with two-tier approval (always/session).
- `freeact/cli.py`: CLI entry point.

## Testing Patterns

- **Unit tests** (`tests/unit/`): Use `FunctionModel(stream_function=...)` for test models. Stream functions receive `(messages, info)` where `info.function_tools` contains available tools.
- **`patched_agent`** (`tests/conftest.py`): Creates an agent with mocked code executor. Use for unit tests that don't need real kernel execution.
- **`unpatched_agent`** (defined locally in integration test files): Creates an agent with real ipybox kernel. Subagent tests must use this since subagents always start real kernels.
- **`collect_stream()`**: Helper that consumes `agent.stream()`, auto-approves via `approve_function`, and collects events into `StreamResults`.
- **`get_tool_return_parts(messages)`**: Detects post-tool-execution model calls (messages ending with `ToolReturnPart`).
- **Distinguishing parent vs subagent** in shared stream functions: Check `"subagent_task" in [t.name for t in info.function_tools]`. Parent has it, subagent does not.
