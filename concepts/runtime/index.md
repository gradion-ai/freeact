# Runtime model

This page explains how a freeact agent runs: how configuration becomes a runtime, how events flow from `stream()`, what happens within a turn, and how subagents and cancellation fit in. For a hands-on introduction, see [First agent with the SDK](https://gradion-ai.github.io/freeact/getting-started/sdk-tutorial/index.md).

## Configuration flow

Configuration flows one way: file, then schema, then resolution. config.load() reads `.freeact/config.toml` into a FreeactConfig (defaults when the file is missing); config.init() additionally initializes the `.freeact/` workspace. config.resolve() turns the parsed config into a ResolvedRuntime: it expands tool presets into server configs, substitutes `${VAR}` references, and prepares the model for pydantic-ai. The Agent is constructed from the resolved runtime.

There is no programmatic save: freeact writes `config.toml` only at `init` and never rewrites it. Edit the file to change configuration. See the [Configuration](https://gradion-ai.github.io/freeact/reference/configuration/index.md) reference for the file format and the `.freeact/` directory structure.

## Lifecycle

The agent manages MCP server connections and an IPython kernel via [ipybox](https://gradion-ai.github.io/ipybox/). On entering the async context manager, the IPython kernel starts and MCP servers configured for JSON tool calling connect. MCP servers configured for programmatic tool calling connect lazily on first tool call.

```
runtime = config.resolve(config.load())
async with Agent(runtime) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Without using the async context manager:

```
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

Each stream() call runs a single agent turn, with the agent managing conversation history across calls. The stream yields events as they occur:

| Event                    | Description                                       |
| ------------------------ | ------------------------------------------------- |
| ThoughtsChunk            | Partial model thoughts (content streaming)        |
| Thoughts                 | Complete model thoughts at a given step           |
| ResponseChunk            | Partial model response (content streaming)        |
| Response                 | Complete model response                           |
| ApprovalRequest          | Pending code action or tool call approval         |
| CodeExecutionOutputChunk | Partial code execution output (content streaming) |
| CodeExecutionOutput      | Complete code execution output                    |
| ToolOutput               | JSON tool call or built-in operation output       |
| Cancelled                | Agent turn was cancelled                          |

All yielded events inherit from AgentEvent and carry `agent_id`. Tool-related events additionally carry a `corr_id` correlating chunks, outputs, and approval requests of the same tool call; events produced by a subagent carry the parent task's correlation id in `parent_corr_id`.

ApprovalRequest events suspend execution until the application resolves them; [Approvals and permissions](https://gradion-ai.github.io/freeact/concepts/approvals/index.md) explains this part of the model. A rejected code action or intercepted sub-command is signaled structurally: the final CodeExecutionOutput has `approval_rejected=True`.

## Internal tools

The agent uses a small set of internal tools for reading and writing files, executing code and commands, spawning subagents, and discovering tools:

| Tool              | Implementation                                      | Description                                                                                                                                                                                 |
| ----------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| read, write, edit | filesystem MCP server                               | Reading, writing, and editing files via JSON tool calls (`filesystem_read_text_file`, `filesystem_read_media_file`, `filesystem_write_text_file`, `filesystem_edit_text_file`)              |
| execute           | `ipybox_execute_ipython_cell`                       | Execution of Python code and shell commands (via `!` syntax), delegated to ipybox's `CodeExecutor`, with shell commands and programmatic MCP tool calls intercepted at runtime for approval |
| subagent          | [`subagent_task`](#subagents)                       | Task delegation to child agents                                                                                                                                                             |
| tool discovery    | `pytools` MCP server for basic and hybrid discovery | Tool discovery via category browsing or hybrid search; enabled with the [`discovery` preset](https://gradion-ai.github.io/freeact/guides/tool-discovery/index.md)                           |

## Turn limits

Use `max_turns` to limit the number of tool-execution rounds before the stream stops:

```
async for event in agent.stream(prompt, max_turns=50):
    ...
```

If `max_turns=None` (default), the loop continues until the model produces a final response.

## Timeouts

The agent supports two timeout settings in [`config.toml`](https://gradion-ai.github.io/freeact/reference/configuration/#agent-settings):

- `execution_timeout`: Maximum time in seconds for each code execution. Approval wait time is excluded from this budget, so the timeout only counts actual execution time. Defaults to 300 seconds. Set to `0` to disable.
- `approval_timeout`: Timeout in seconds for approval requests. An approval request that is not resolved within this time is rejected. Defaults to `0` (wait forever).

```
[agent]
execution_timeout = 60.0
approval_timeout = 30.0
```

## Subagents

The built-in `subagent_task` tool delegates a subtask to a child agent with a fresh IPython kernel and fresh MCP server connections. The child inherits model, system prompt, and sandbox settings from the parent. Its events flow through the parent's stream using the same [approval](https://gradion-ai.github.io/freeact/concepts/approvals/index.md) mechanism, with `agent_id` identifying the source:

```
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest(agent_id=agent_id, tool_call=tool_call) as request:
            print(f"[{agent_id}] Approve {tool_call}?")
            request.approve(True)
        case Response(content=content, agent_id=agent_id):
            print(f"[{agent_id}] {content}")
```

The main agent's `agent_id` is `main`, subagent IDs use the form `sub-xxxx`. Each delegated task defaults to `max_turns=100`. The [`max_subagents`](https://gradion-ai.github.io/freeact/reference/configuration/#agent-settings) setting in `config.toml` limits concurrent subagents (default 5).

## Cancellation

Call cancel() to stop a running agent turn. The active `stream()` stops at the next phase boundary and yields a Cancelled event whose `phase` field is a Phase value identifying the interrupted phase. Running kernel executions, including those in subagents, are interrupted immediately. Partial responses and synthetic tool returns are preserved in message history, so the conversation remains consistent for subsequent turns.

```
# From another coroutine or callback:
agent.cancel()
```

```
async for event in agent.stream(prompt):
    match event:
        case Cancelled(phase=phase):
            print(f"Turn cancelled during {phase}")
        case Response(content=content):
            print(content)
```

## Sessions

The agent persists message history incrementally to `.freeact/sessions/<session-id>/<agent-id>.jsonl` while it runs (unless `enable_persistence` is `false`). On resume, only the main agent's history (`main.jsonl`) is rehydrated; subagent histories (`sub-xxxx.jsonl`) are persisted for auditing only. Results exceeding an inline size threshold are stored as files in the session directory and referenced from the history. See [Persist and resume sessions](https://gradion-ai.github.io/freeact/guides/sessions/index.md) for creating, resuming, and configuring sessions.
