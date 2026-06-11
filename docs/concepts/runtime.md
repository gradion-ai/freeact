# Runtime model

This page explains how a freeact agent runs: how configuration becomes a runtime, how events flow from `stream()`, what happens within a turn, and how subagents and cancellation fit in. For a hands-on introduction, see [First agent with the SDK](../getting-started/sdk-tutorial.md).

## Configuration flow

Configuration flows one way: file, then schema, then resolution. [`config.load()`][freeact.config.load] reads `.freeact/config.toml` into a [`FreeactConfig`][freeact.config.FreeactConfig] (defaults when the file is missing); [`config.init()`][freeact.config.init] additionally initializes the `.freeact/` workspace. [`config.resolve()`][freeact.config.resolve] turns the parsed config into a [`ResolvedRuntime`][freeact.config.ResolvedRuntime]: it expands tool presets into server configs, substitutes `${VAR}` references, and prepares the model for pydantic-ai. The [`Agent`][freeact.Agent] is constructed from the resolved runtime.

There is no programmatic save: freeact writes `config.toml` only at `init` and never rewrites it. Edit the file to change configuration. See the [Configuration](../reference/configuration.md) reference for the file format and the `.freeact/` directory structure.

## Lifecycle

The agent manages MCP server connections and an IPython kernel via [ipybox](https://gradion-ai.github.io/ipybox/). On entering the async context manager, the IPython kernel starts and MCP servers configured for JSON tool calling connect. MCP servers configured for programmatic tool calling connect lazily on first tool call.

```python
runtime = config.resolve(config.load())
async with Agent(runtime) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Without using the async context manager:

```python
runtime = config.resolve(config.load())
agent = Agent(runtime)
await agent.start()
try:
    async for event in agent.stream(prompt):
        ...
finally:
    await agent.stop()
```

## Events

Each [`stream()`][freeact.Agent.stream] call runs a single agent turn, with the agent managing conversation history across calls. The stream yields events as they occur:

| Event | Description |
|-------|-------------|
| [`ThoughtsChunk`][freeact.ThoughtsChunk] | Partial model thoughts (content streaming) |
| [`Thoughts`][freeact.Thoughts] | Complete model thoughts at a given step |
| [`ResponseChunk`][freeact.ResponseChunk] | Partial model response (content streaming) |
| [`Response`][freeact.Response] | Complete model response |
| [`ApprovalRequest`][freeact.ApprovalRequest] | Pending code action or tool call approval |
| [`CodeExecutionOutputChunk`][freeact.CodeExecutionOutputChunk] | Partial code execution output (content streaming) |
| [`CodeExecutionOutput`][freeact.CodeExecutionOutput] | Complete code execution output |
| [`ToolOutput`][freeact.ToolOutput] | JSON tool call or built-in operation output |
| [`Cancelled`][freeact.Cancelled] | Agent turn was cancelled |

All yielded events inherit from [`AgentEvent`][freeact.AgentEvent] and carry `agent_id`. Tool-related events additionally carry a `corr_id` correlating chunks, outputs, and approval requests of the same tool call; events produced by a subagent carry the parent task's correlation id in `parent_corr_id`.

[`ApprovalRequest`][freeact.ApprovalRequest] events suspend execution until the application resolves them; [Approvals and permissions](approvals.md) explains this part of the model. A rejected code action or intercepted sub-command is signaled structurally: the final [`CodeExecutionOutput`][freeact.CodeExecutionOutput] has `approval_rejected=True`.

## Internal tools

The agent uses a small set of internal tools for reading and writing files, executing code and commands, spawning subagents, and discovering tools:

| Tool | Implementation | Description |
|------|---------------|-------------|
| read, write, edit | [`filesystem`][freeact.config.FILESYSTEM_MCP_SERVER_CONFIG] MCP server | Reading, writing, and editing files via JSON tool calls (`filesystem_read_text_file`, `filesystem_read_media_file`, `filesystem_write_text_file`, `filesystem_edit_text_file`) |
| execute | `ipybox_execute_ipython_cell` | Execution of Python code and shell commands (via `!` syntax), delegated to ipybox's `CodeExecutor`, with shell commands and programmatic MCP tool calls intercepted at runtime for approval |
| subagent | [`subagent_task`](#subagents) | Task delegation to child agents |
| tool discovery | `pytools` MCP server for [basic][freeact.config.BASIC_SEARCH_MCP_SERVER_CONFIG] and [hybrid][freeact.config.HYBRID_SEARCH_MCP_SERVER_CONFIG] discovery | Tool discovery via category browsing or hybrid search; enabled with the [`discovery` preset](../guides/tool-discovery.md) |

## Turn limits

Use `max_turns` to limit the number of tool-execution rounds before the stream stops:

```python
async for event in agent.stream(prompt, max_turns=50):
    ...
```

If `max_turns=None` (default), the loop continues until the model produces a final response.

## Timeouts

The agent supports two timeout settings in [`config.toml`](../reference/configuration.md#agent-settings):

- `execution_timeout`: Maximum time in seconds for each code execution. Approval wait time is excluded from this budget, so the timeout only counts actual execution time. Defaults to 300 seconds. Set to `0` to disable.
- `approval_timeout`: Timeout in seconds for approval requests. An approval request that is not resolved within this time is rejected. Defaults to `0` (wait forever).

```toml
[agent]
execution_timeout = 60.0
approval_timeout = 30.0
```

## Subagents

The built-in `subagent_task` tool delegates a subtask to a child agent with a fresh IPython kernel and fresh MCP server connections. The child inherits model, system prompt, and sandbox settings from the parent. Its events flow through the parent's stream using the same [approval](approvals.md) mechanism, with `agent_id` identifying the source:

```python
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest(agent_id=agent_id, tool_call=tool_call) as request:
            print(f"[{agent_id}] Approve {tool_call}?")
            request.approve(True)
        case Response(content=content, agent_id=agent_id):
            print(f"[{agent_id}] {content}")
```

The main agent's `agent_id` is `main`, subagent IDs use the form `sub-xxxx`. Each delegated task defaults to `max_turns=100`. The [`max_subagents`](../reference/configuration.md#agent-settings) setting in `config.toml` limits concurrent subagents (default 5).

## Cancellation

Call [`cancel()`][freeact.Agent.cancel] to stop a running agent turn. The active `stream()` stops at the next phase boundary and yields a [`Cancelled`][freeact.Cancelled] event whose `phase` field is a [`Phase`][freeact.Phase] value identifying the interrupted phase. Running kernel executions, including those in subagents, are interrupted immediately. Partial responses and synthetic tool returns are preserved in message history, so the conversation remains consistent for subsequent turns.

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

## Sessions

The agent persists message history incrementally to `.freeact/sessions/<session-id>/<agent-id>.jsonl` while it runs (unless `enable_persistence` is `false`). On resume, only the main agent's history (`main.jsonl`) is rehydrated; subagent histories (`sub-xxxx.jsonl`) are persisted for auditing only. Results exceeding an inline size threshold are stored as files in the session directory and referenced from the history. See [Persist and resume sessions](../guides/sessions.md) for creating, resuming, and configuring sessions.
