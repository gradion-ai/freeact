# Agent SDK

The Agent SDK provides four main APIs:

- [Configuration API](api/config.md) for initializing and loading configuration from `.freeact/`
- [Generation API](api/generate.md) for generating Python APIs for MCP server tools
- [Agent API](api/agent.md) for running the agentic code action loop
- [Permissions API](api/permissions.md) for managing approval decisions

## Configuration API

Use [`Config.init()`][freeact.agent.config.Config.init] to scaffold the `.freeact/` directory from default templates. The [`Config()`][freeact.agent.config.Config] constructor loads all configuration from it:

```python
--8<-- "examples/basic_agent.py:config-imports"
--8<-- "examples/basic_agent.py:config"
```

See the [Configuration](configuration.md) reference for details on the `.freeact/` directory structure.

## Generation API

MCP servers [configured](configuration.md#ptc-servers) as `ptc-servers` in `config.json` require Python API generation with [`generate_mcp_sources()`][freeact.tools.pytools.apigen.generate_mcp_sources] before the agent can call their tools programmatically:

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

All yielded events inherit from [`AgentEvent`][freeact.agent.AgentEvent] and carry `agent_id`.

### Internal tools

The agent uses a small set of internal tools for reading and writing files, executing code and commands, spawning subagents, and discovering tools:

| Tool | Implementation | Description |
|------|---------------|-------------|
| read, write | [`filesystem`][freeact.agent.config.FILESYSTEM_CONFIG] MCP server | Reading and writing files via JSON tool calls |
| execute | `ipybox_execute_ipython_cell` | Execution of Python code and shell commands (via `!` prefix), delegated to ipybox's `CodeExecutor` |
| subagent | [`subagent_task`](#subagents) | Task delegation to child agents |
| tool search | `pytools` MCP server for [basic search][freeact.agent.config.PYTOOLS_BASIC_CONFIG] and [hybrid search][freeact.agent.config.PYTOOLS_HYBRID_CONFIG] | Tool discovery via category browsing or hybrid search |

### Turn limits

Use `max_turns` to limit the number of tool-execution rounds before the stream stops:

```python
async for event in agent.stream(prompt, max_turns=50):
    ...
```

If `max_turns=None` (default), the loop continues until the model produces a final response.

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

The main agent's `agent_id` is `main`, subagent IDs use the form `sub-xxxx`. Each delegated task defaults to `max_turns=100`. The [`max-subagents`](configuration.md#agent-settings) setting in `config.json` limits concurrent subagents (default 5).

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
config = Config()
async with Agent(config=config) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Without using the async context manager:

```python
config = Config()
agent = Agent(config=config)
await agent.start()
try:
    async for event in agent.stream(prompt):
        ...
finally:
    await agent.stop()
```

### Timeouts

The agent supports two timeout settings in [`config.json`](configuration.md#agent-settings):

- **`execution-timeout`**: Maximum time in seconds for each [code execution](execution.md). Approval wait time is excluded from this budget, so the timeout only counts actual execution time. Defaults to 300 seconds. Set to `null` to disable.
- **`approval-timeout`**: Timeout for approval requests during programmatic tool calls. If an approval request is not accepted or rejected within this time, the tool call fails. Defaults to `null` (no timeout).

```json
{
  "execution-timeout": 60,
  "approval-timeout": 30
}
```

### Persistence

[`SessionStore`][freeact.agent.store.SessionStore] persists agent message history to `.freeact/sessions/<session-uuid>/<agent-id>.jsonl`. Each agent turn appends messages incrementally, so the history is durable even if the process terminates mid-session.

```python
--8<-- "examples/persistent_agent.py:session-imports"
--8<-- "examples/persistent_agent.py:session-create"
```

Pass the store to [`Agent`][freeact.agent.Agent] to enable persistence.

```python
--8<-- "examples/persistent_agent.py:session-run"
```

To resume a session, create a new `SessionStore` with the same `session_id`. The agent loads the persisted message history on startup and continues from where it left off.

```python
--8<-- "examples/persistent_agent.py:session-resume"
```

Only the main agent's message history (`main.jsonl`) is loaded on resume. Subagent messages are persisted to separate files (`sub-xxxx.jsonl`) for auditing but are not rehydrated.

The [CLI tool](cli.md) accepts `--session-id` to resume a session from the command line.

## Permissions API

!!! info "Work in progress"

    Current permission management is preliminary and will be reimplemented in a future release.

The agent requests approval for each code action and tool call but doesn't remember past decisions. [`PermissionManager`][freeact.permissions.PermissionManager] adds memory: `allow_always()` persists to `.freeact/permissions.json`, while `allow_session()` stores in-memory until the session ends:

```python
from freeact.permissions import PermissionManager
from ipybox.utils import arun

manager = PermissionManager()
await manager.load()

async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest() as request:
            if manager.is_allowed(request.tool_name, request.tool_args):
                request.approve(True)
            else:
                choice = await arun(input, "Allow? [Y/n/a/s]: ")
                match choice:
                    case "a":
                        await manager.allow_always(request.tool_name)
                        request.approve(True)
                    case "s":
                        manager.allow_session(request.tool_name)
                        request.approve(True)
                    case "n":
                        request.approve(False)
                    case _:
                        request.approve(True)
```
