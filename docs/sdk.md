# Agent SDK

The Agent SDK provides five main APIs:

- [Configuration API](#configuration-api) for initializing and loading configuration from `.freeact/`
- [Generation API](#generation-api) for generating Python APIs for MCP server tools
- [Agent API](#agent-api) for running the agentic code action loop
- [Permissions API](#permissions-api) for managing approval decisions
- [Preprocessing API](#preprocessing-api) for transforming user prompts

## Configuration API

Use [`Config.init()`][freeact.config.PersistentConfig.init] to load persisted config from `.freeact/` when present, or create and save defaults on first run. Use [`save()`][freeact.config.PersistentConfig.save] and [`load()`][freeact.config.PersistentConfig.load] when explicit persistence control is needed:

```python
--8<-- "examples/basic_agent.py:config-imports"
--8<-- "examples/basic_agent.py:config"
```

See the [Configuration](configuration.md) reference for details on the `.freeact/` directory structure.

## Generation API

MCP servers [configured](configuration.md#ptc_servers) as `ptc_servers` in `agent.json` require Python API generation with [`generate_mcp_sources()`][freeact.tools.pytools.apigen.generate_mcp_sources] before the agent can call their tools programmatically:

```python
--8<-- "examples/basic_agent.py:apigen-imports"
--8<-- "examples/basic_agent.py:apigen"
```

Generated APIs are stored as `.freeact/generated/mcptools/<server_name>/<tool>.py` modules and persist across agent sessions. The `.freeact/generated/` directory is on the kernel's `PYTHONPATH`, so the agent can import them directly:

```python
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
```

## Agent API

The [`Agent`][freeact.agent.Agent] class implements the agentic code action loop, handling code action generation, [code execution](execution.md), tool calls, and the approval workflow. Each [`stream()`][freeact.agent.Agent.stream] call runs a single agent turn, with the agent managing conversation history across calls. Use `stream()` to iterate over [events](#events) and handle them with pattern matching:

```python
--8<-- "examples/basic_agent.py:agent-imports"
--8<-- "examples/basic_agent.py:agent"
```

For processing output incrementally, match the `*Chunk` event variants listed below.

### Events

The [`Agent.stream()`][freeact.agent.Agent.stream] method yields events as they occur:

| Event | Description |
|-------|-------------|
| [`ThoughtsChunk`][freeact.agent.ThoughtsChunk] | Partial model thoughts (content streaming) |
| [`Thoughts`][freeact.agent.Thoughts] | Complete model thoughts at a given step |
| [`ResponseChunk`][freeact.agent.ResponseChunk] | Partial model response (content streaming) |
| [`Response`][freeact.agent.Response] | Complete model response |
| [`ApprovalRequest`][freeact.agent.ApprovalRequest] | Pending code action or tool call approval |
| [`CodeExecutionOutputChunk`][freeact.agent.CodeExecutionOutputChunk] | Partial code execution output (content streaming) |
| [`CodeExecutionOutput`][freeact.agent.CodeExecutionOutput] | Complete code execution output |
| [`ToolOutput`][freeact.agent.ToolOutput] | Tool or built-in operation output |
| [`Cancelled`][freeact.agent.Cancelled] | Agent turn was cancelled |

All yielded events inherit from [`AgentEvent`][freeact.agent.AgentEvent] and carry `agent_id`.

### Internal tools

The agent uses a small set of internal tools for reading and writing files, executing code and commands, spawning subagents, and discovering tools:

| Tool | Implementation | Description |
|------|---------------|-------------|
| read, write | [`filesystem`][freeact.agent.config.FILESYSTEM_MCP_SERVER_CONFIG] MCP server | Reading and writing files via JSON tool calls |
| execute | `ipybox_execute_ipython_cell` | Execution of Python code and shell commands (via `!` prefix), delegated to ipybox's `CodeExecutor` |
| subagent | [`subagent_task`](#subagents) | Task delegation to child agents |
| tool search | `pytools` MCP server for [basic search][freeact.agent.config.BASIC_SEARCH_MCP_SERVER_CONFIG] and [hybrid search][freeact.agent.config.HYBRID_SEARCH_MCP_SERVER_CONFIG] | Tool discovery via category browsing or hybrid search |

### Turn limits

Use `max_turns` to limit the number of tool-execution rounds before the stream stops:

```python
async for event in agent.stream(prompt, max_turns=50):
    ...
```

If `max_turns=None` (default), the loop continues until the model produces a final response.

### Cancellation

Call [`cancel()`][freeact.agent.Agent.cancel] to stop a running agent turn. The active `stream()` stops at the next phase boundary and yields a [`Cancelled`][freeact.agent.Cancelled] event. Running kernel executions, including those in subagents, are interrupted immediately. Partial responses and synthetic tool returns are preserved in message history, so the conversation remains consistent for subsequent turns.

```python
# From another coroutine or callback:
agent.cancel()
```

```python
async for event in agent.stream(prompt):
    match event:
        case Cancelled(phase=phase):
            print(f"Turn cancelled during {phase}")
        case Response(content=content):
            print(content)
```

### Subagents

The built-in `subagent_task` tool delegates a subtask to a child agent with a fresh IPython kernel and fresh MCP server connections. The child inherits model, system prompt, and sandbox settings from the parent. Its events flow through the parent's stream using the same [approval](#approval) mechanism, with `agent_id` identifying the source:

```python
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest(agent_id=agent_id) as request:
            print(f"[{agent_id}] Approve {request.tool_name}?")
            request.approve(True)
        case Response(content=content, agent_id=agent_id):
            print(f"[{agent_id}] {content}")
```

The main agent's `agent_id` is `main`, subagent IDs use the form `sub-xxxx`. Each delegated task defaults to `max_turns=100`. The [`max_subagents`](configuration.md#agent-settings) setting in `agent.json` limits concurrent subagents (default 5).

### Approval

The agent provides a unified approval mechanism. It yields [`ApprovalRequest`][freeact.agent.ApprovalRequest] for all code actions, programmatic tool calls, and JSON tool calls. Execution is suspended until `approve()` is called. Calling `approve(True)` executes the code action or tool call; `approve(False)` rejects it and ends the current agent turn.

```python
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest() as request:
            # Inspect the pending action
            print(f"Tool: {request.tool_name}")
            print(f"Args: {request.tool_args}")

            # Approve or reject
            request.approve(True)

        case Response(content=content):
            print(content)
```

!!! note "Code action approval"

    For code actions, `tool_name` is `ipybox_execute_ipython_cell` and `tool_args` contains the `code` to execute.

### Lifecycle

The agent manages MCP server connections and an IPython kernel via [ipybox](https://gradion-ai.github.io/ipybox/). On entering the async context manager, the IPython kernel starts and MCP servers configured for JSON tool calling connect. MCP servers configured for programmatic tool calling connect lazily on first tool call.

```python
config = await Config.init()
async with Agent(config=config) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Without using the async context manager:

```python
config = await Config.init()
agent = Agent(config=config)
await agent.start()
try:
    async for event in agent.stream(prompt):
        ...
finally:
    await agent.stop()
```

### Timeouts

The agent supports two timeout settings in [`agent.json`](configuration.md#agent-settings):

- `execution_timeout`: Maximum time in seconds for each [code execution](execution.md). Approval wait time is excluded from this budget, so the timeout only counts actual execution time. Defaults to 300 seconds. Set to `null` to disable.
- `approval_timeout`: Timeout for approval requests during programmatic tool calls. If an approval request is not accepted or rejected within this time, the tool call fails. Defaults to `null` (no timeout).

```json
{
  "execution_timeout": 60,
  "approval_timeout": 30
}
```

### Persistence

[`Config`][freeact.agent.config.Config] controls session persistence via `enable_persistence`.

- Default: `true`. The agent persists history to `.freeact/sessions/<session-id>/<agent-id>.jsonl`.
- `false`: The agent keeps history in memory only. Passing `session_id` to [`Agent`][freeact.agent.Agent] raises `ValueError`.

When persistence is enabled, construct an agent without `session_id` to create a new session ID internally. Read it from `agent.session_id`:

```python
--8<-- "examples/persistent_agent.py:session-run-no-id"
```

Construct an agent with an explicit `session_id` for create-or-resume behavior:

```python
--8<-- "examples/persistent_agent.py:session-create"
--8<-- "examples/persistent_agent.py:session-run-existing"
```

If that `session_id` already exists, the persisted history is resumed. If it does not exist, a new session starts with that ID.

To resume later, create another agent with the same `session_id`:

```python
--8<-- "examples/persistent_agent.py:session-resume"
```

Only the main agent's message history (`main.jsonl`) is loaded on resume. Subagent messages are persisted to separate files (`sub-xxxx.jsonl`) for auditing but are not rehydrated.

The [CLI tool](cli.md) accepts `--session-id` to resume a session from the command line when `enable_persistence` is `true`.

#### Tool Results

Tool result persistence handles outputs that are too large to keep inline in the message history. Large inline payloads can bloat context and slow down processing. When a result exceeds the inline size threshold, the full content is saved to disk and replaced inline with a short file reference notice that includes a preview.

Tool result persistence is controlled by two config options:

- `tool_result_inline_max_bytes`: Maximum inline payload size for a tool result.
- `tool_result_preview_chars`: Number of preview characters shown from both the beginning and end of large text results in the file reference notice.

## Permissions API

[`PermissionManager`][freeact.permissions.PermissionManager] provides pattern-based permission gating using typed [`ToolCall`][freeact.agent.call.ToolCall] instances. Patterns use glob-style matching (`*`, `?`). Path fields use path-aware matching where `*` matches within a single directory and `**` matches across directory boundaries. Rules are organized into ask/allow tiers with session and always persistence scopes.

Each `ApprovalRequest` carries a `tool_call` field that is a `ToolCall` subclass (`GenericCall`, `ShellAction`, `CodeAction`, `FileRead`, `FileWrite`, `FileEdit`). Permission matching is type-specific: shell commands match on `command`, filesystem tools match on `path`/`paths`, and generic tools match on `tool_name` only.

```python
from freeact.permissions import PermissionManager
from freeact.agent import suggest_pattern

manager = PermissionManager()
await manager.init()

async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest() as request:
            if manager.is_allowed(request.tool_call):
                request.approve(True)
            else:
                pattern = suggest_pattern(request.tool_call)
                choice = input(f"Allow [{pattern}]? [Y/n/a/s]: ")
                match choice:
                    case "a":
                        await manager.allow_always(request.tool_call)
                        request.approve(True)
                    case "s":
                        manager.allow_session(request.tool_call)
                        request.approve(True)
                    case "n":
                        request.approve(False)
                    case _:
                        request.approve(True)
```

See [Permissions](configuration.md#permissions) for the persisted file format and pattern syntax.

## Preprocessing API

The terminal UI converts user-facing syntax (`/skill-name` and `@path`) into XML tags, then [`preprocess_prompt`][freeact.preproc.preprocess_prompt] transforms the tagged text into agent-ready content. Attachment tags are resolved to multimodal content with image data. Skill tags pass through to the agent unchanged.

A `/skill-name` command becomes a `<skill>` tag that the agent handles via skill metadata in its system prompt:

```python
--8<-- "examples/prompt_preproc.py:skill"
```

An `@path` reference becomes an `<attachment path="..."/>` tag. [`preprocess_prompt`][freeact.preproc.preprocess_prompt] resolves image paths to binary content:

```python
--8<-- "examples/prompt_preproc.py:attachment"
```

Plain text passes through unchanged:

```python
--8<-- "examples/prompt_preproc.py:plain"
```
