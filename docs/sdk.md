# Agent SDK

The Agent SDK provides four main APIs:

- [Configuration API](#configuration-api) for loading and resolving configuration from `.freeact/`
- [Generation API](#generation-api) for generating Python APIs for MCP server tools
- [Agent API](#agent-api) for running the agentic code action loop
- [Permissions API](#permissions-api) for managing approval decisions

## Configuration API

Configuration flows one way: file, then schema, then resolution. [`config.load()`][freeact.config.load] reads `.freeact/config.toml` into a [`FreeactConfig`][freeact.config.FreeactConfig] (defaults when the file is missing); [`config.init()`][freeact.config.init] additionally initializes the `.freeact/` workspace (writes the commented default `config.toml` when missing, creates runtime directories, materializes bundled skills). [`config.resolve()`][freeact.config.resolve] turns the parsed config into a [`ResolvedRuntime`][freeact.config.ResolvedRuntime]: it expands [tool presets](configuration.md#tool-presets) into server configs, substitutes `${VAR}` references, and prepares the model for pydantic-ai. The [`Agent`](#agent-api) is constructed from the resolved runtime:

```python
--8<-- "examples/basic_agent.py:config-imports"
--8<-- "examples/basic_agent.py:config"
```

There is no programmatic save: freeact writes `config.toml` only at `init` and never rewrites it. Edit the file to change configuration. See the [Configuration](configuration.md) reference for the file format and the `.freeact/` directory structure.

## Generation API

MCP servers [configured](configuration.md#ptc_servers) as `ptc_servers` in `config.toml` require Python API generation with [`generate_mcp_sources()`][freeact.tools.pytools.apigen.generate_mcp_sources] before the agent can call their tools programmatically:

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

The [`Agent`][freeact.Agent] class implements the agentic code action loop, handling code action generation, [code execution](execution.md), tool calls, and the approval workflow. Each [`stream()`][freeact.Agent.stream] call runs a single agent turn, with the agent managing conversation history across calls. Use `stream()` to iterate over [events](#events) and handle them with pattern matching:

```python
--8<-- "examples/basic_agent.py:agent"
```

For processing output incrementally, match the `*Chunk` event variants listed below.

### Events

The [`Agent.stream()`][freeact.Agent.stream] method yields events as they occur:

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

A rejected code action or intercepted sub-command is signaled structurally: the final [`CodeExecutionOutput`][freeact.CodeExecutionOutput] has `approval_rejected=True`.

### Internal tools

The agent uses a small set of internal tools for reading and writing files, executing code and commands, spawning subagents, and discovering tools:

| Tool | Implementation | Description |
|------|---------------|-------------|
| read, write, edit | [`filesystem`][freeact.config.FILESYSTEM_MCP_SERVER_CONFIG] MCP server | Reading, writing, and editing files via JSON tool calls (`filesystem_read_text_file`, `filesystem_read_media_file`, `filesystem_write_text_file`, `filesystem_edit_text_file`) |
| execute | `ipybox_execute_ipython_cell` | Execution of Python code and shell commands (via `!` syntax), delegated to ipybox's `CodeExecutor`, with shell commands and programmatic MCP tool calls intercepted at runtime for approval |
| subagent | [`subagent_task`](#subagents) | Task delegation to child agents |
| tool discovery | `pytools` MCP server for [basic][freeact.config.BASIC_SEARCH_MCP_SERVER_CONFIG] and [hybrid][freeact.config.HYBRID_SEARCH_MCP_SERVER_CONFIG] discovery | Tool discovery via category browsing or hybrid search; enabled with the [`discovery` preset](configuration.md#tool-presets) |

### Turn limits

Use `max_turns` to limit the number of tool-execution rounds before the stream stops:

```python
async for event in agent.stream(prompt, max_turns=50):
    ...
```

If `max_turns=None` (default), the loop continues until the model produces a final response.

### Cancellation

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

### Subagents

The built-in `subagent_task` tool delegates a subtask to a child agent with a fresh IPython kernel and fresh MCP server connections. The child inherits model, system prompt, and sandbox settings from the parent. Its events flow through the parent's stream using the same [approval](#approval) mechanism, with `agent_id` identifying the source:

```python
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest(agent_id=agent_id, tool_call=tool_call) as request:
            print(f"[{agent_id}] Approve {tool_call}?")
            request.approve(True)
        case Response(content=content, agent_id=agent_id):
            print(f"[{agent_id}] {content}")
```

The main agent's `agent_id` is `main`, subagent IDs use the form `sub-xxxx`. Each delegated task defaults to `max_turns=100`. The [`max_subagents`](configuration.md#agent-settings) setting in `config.toml` limits concurrent subagents (default 5).

### Approval

The agent yields [`ApprovalRequest`][freeact.ApprovalRequest] for code actions and each shell command and programmatic tool call within them. Each request carries a [`tool_call`][freeact.ToolCall] field identifying the pending action. Execution is suspended until `approve()` is called. Calling `approve(True)` executes the action; `approve(False)` rejects it and ends the current agent turn.

```python
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest(tool_call=CodeAction(code=code)) as request:
            print(f"Code action:\n{code}")
            request.approve(True)
        case ApprovalRequest(tool_call=ShellAction(command=cmd)) as request:
            print(f"Shell command: {cmd}")
            request.approve(True)
        case ApprovalRequest(tool_call=GenericCall(tool_name=name, ptc=True)) as request:
            print(f"Programmatic tool call: {name}")
            request.approve(True)
        case ApprovalRequest(tool_call=GenericCall(tool_name=name)) as request:
            print(f"JSON tool call: {name}")
            request.approve(True)
        case Response(content=content):
            print(content)
```

The `tool_call` type determines what is being approved:

| `tool_call` type | Trigger |
|---|---|
| [`CodeAction`][freeact.CodeAction] | Code action containing Python code and shell commands to execute |
| [`ShellAction`][freeact.ShellAction] | Shell command (`!cmd`) or shell script (`%%bash`) intercepted during code action execution |
| [`GenericCall`][freeact.GenericCall] | Programmatic tool call (intercepted during code action execution) or JSON tool call |
| [`FileRead`][freeact.FileRead], [`FileWrite`][freeact.FileWrite], [`FileEdit`][freeact.FileEdit] | Filesystem operation via built-in MCP server |

Shell commands and programmatic tool calls within code actions are intercepted during execution and yield separate `ApprovalRequest` events. Composite shell commands (using `&&`, `||`, `|`, `;`) are decomposed into individual sub-commands, each requiring separate approval. Python variables in shell commands are resolved before the approval request.

If the consumer abandons the stream while an approval is pending, the request is resolved as rejected. With a configured [`approval_timeout`](#timeouts), an unresolved request is rejected when the timeout expires.

### Lifecycle

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

### Timeouts

The agent supports two timeout settings in [`config.toml`](configuration.md#agent-settings):

- `execution_timeout`: Maximum time in seconds for each [code execution](execution.md). Approval wait time is excluded from this budget, so the timeout only counts actual execution time. Defaults to 300 seconds. Set to `0` to disable.
- `approval_timeout`: Timeout in seconds for [approval requests](#approval). An approval request that is not resolved within this time is rejected. Defaults to `0` (wait forever).

```toml
[agent]
execution_timeout = 60.0
approval_timeout = 30.0
```

### Persistence

#### Sessions

The `enable_persistence` setting in the [`[agent]` section](configuration.md#agent-settings) controls session persistence.

- Default: `true`. The agent persists history to `.freeact/sessions/<session-id>/<agent-id>.jsonl`.
- `false`: The agent keeps history in memory only. Passing `session_id` to [`Agent`][freeact.Agent] raises `ValueError`.

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

#### Results

Tool call results, code execution outputs, and subagent responses are checked against an inline size threshold before being added to the message history. When a result exceeds the threshold, the full content is saved to disk and replaced inline with a file reference notice that includes a preview. This prevents large outputs from bloating context.

Controlled by two config options:

- `tool_result_inline_max_bytes`: Maximum inline payload size in bytes.
- `tool_result_preview_chars`: Number of preview characters from both the beginning and end of large text results included in the file reference notice.

### Prompt tags

Prompts passed to `stream()` may contain skill tags that the agent processes. Skill tags explicitly invoke a skill by name. The [CLI tool](cli.md#skill-invocation) generates these from `/skill-name` syntax.

```xml
<skill name="review">the auth module</skill>
```

Without an explicit tag, the agent can still autonomously select a skill when the request matches a skill's description. Skills are discovered from `.freeact/skills/` and `.agents/skills/` directories.

## Permissions API

The agent does not enforce permissions itself. It yields [`ApprovalRequest`](#approval) events and leaves the decision to the application. [`PermissionManager`][freeact.PermissionManager] is an optional utility that applications can use to automate those decisions based on stored rules. The [CLI tool](cli.md#approval-prompt) uses it internally; SDK applications can use it the same way.

The manager loads and saves rules from `.freeact/permissions.toml`. Rules are typed, glob-style [patterns](configuration.md#permissions) organized into two tiers (allow and ask) and two persistence scopes (always and session). See [Permissions](configuration.md#permissions) for the file format, pattern syntax, and matching semantics.

The core API:

- [`init()`][freeact.permissions.PermissionManager.init] loads rules from `.freeact/permissions.toml` if present, otherwise saves defaults.
- [`is_allowed(tool_call)`][freeact.permissions.PermissionManager.is_allowed] checks a concrete tool call (literal values, no wildcards) against stored rules.
- [`allow_always(tool_call)`][freeact.permissions.PermissionManager.allow_always] adds a rule and persists it to `permissions.toml`. The tool call fields may contain glob wildcards to match broadly (e.g., `command="git *"`).
- [`allow_session(tool_call)`][freeact.permissions.PermissionManager.allow_session] adds an in-memory rule for the current session. Same wildcard support as `allow_always`.

```python
import asyncio
from freeact import ApprovalRequest, PermissionManager, suggest_pattern

loop = asyncio.get_running_loop()

manager = PermissionManager()
await loop.run_in_executor(None, manager.init)

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
                        await loop.run_in_executor(
                            None, 
                            manager.allow_always, 
                            request.tool_call,
                        )
                        request.approve(True)
                    case "s":
                        manager.allow_session(request.tool_call)
                        request.approve(True)
                    case "n":
                        request.approve(False)
                    case _:
                        request.approve(True)
```

For shell commands, [`suggest_display(tool_call)`][freeact.suggest_display] returns the verbatim command (or a first-line summary for `%%bash` shell magic) and is suitable for displaying in the prompt instead of the permission pattern. It returns an empty string for non-shell tool calls, so applications can fall back to `suggest_pattern()` in that case.
