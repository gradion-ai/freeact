# Agent SDK

The Agent SDK provides four main APIs:

- [Configuration API](#configuration-api) for initializing and loading configuration from `.freeact/`
- [Generation API](#generation-api) for generating Python APIs for MCP server tools
- [Agent API](#agent-api) for running the agentic code action loop
- [Permissions API](#permissions-api) for managing approval decisions

## Configuration API

Use Config.init() to load persisted config from `.freeact/` when present, or create and save defaults on first run. Use save() and load() when explicit persistence control is needed:

```
from freeact.agent.config import Config

config = await Config.init()
```

See the [Configuration](https://gradion-ai.github.io/freeact/configuration/index.md) reference for details on the `.freeact/` directory structure.

## Generation API

MCP servers [configured](https://gradion-ai.github.io/freeact/configuration/#ptc_servers) as `ptc_servers` in `agent.json` require Python API generation with generate_mcp_sources() before the agent can call their tools programmatically:

```
from freeact.tools.pytools.apigen import generate_mcp_sources

# Generate Python APIs for MCP servers in ptc_servers
for server_name, params in config.ptc_servers.items():
    if not (config.generated_dir / "mcptools" / server_name).exists():
        await generate_mcp_sources({server_name: params}, config.generated_dir)
```

Generated APIs are stored as `.freeact/generated/mcptools/<server_name>/<tool>.py` modules and persist across agent sessions. The `.freeact/generated/` directory is on the kernel's `PYTHONPATH`, so the agent can import them directly:

```
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
```

## Agent API

The Agent class implements the agentic code action loop, handling code action generation, [code execution](https://gradion-ai.github.io/freeact/execution/index.md), tool calls, and the approval workflow. Each stream() call runs a single agent turn, with the agent managing conversation history across calls. Use `stream()` to iterate over [events](#events) and handle them with pattern matching:

```
from freeact.agent import (
    Agent,
    ApprovalRequest,
    CodeAction,
    CodeExecutionOutput,
    Response,
    ShellAction,
    Thoughts,
    ToolOutput,
)

async with Agent(config=config) as agent:
    prompt = "Who is the F1 world champion 2025?"

    async for event in agent.stream(prompt):
        match event:
            case ApprovalRequest(tool_call=CodeAction(code=code)) as request:
                print(f"Code action:\n{code}")
                request.approve(True)
            case ApprovalRequest(tool_call=ShellAction(command=cmd)) as request:
                print(f"Shell command: {cmd}")
                request.approve(True)
            case ApprovalRequest(tool_call=tool_call) as request:
                print(f"Tool: {tool_call.tool_name}")
                request.approve(True)
            case Thoughts(content=content):
                print(f"Thinking: {content}")
            case CodeExecutionOutput(text=text):
                print(f"Code execution output: {text}")
            case ToolOutput(content=content):
                print(f"Tool call result: {content}")
            case Response(content=content):
                print(content)
```

For processing output incrementally, match the `*Chunk` event variants listed below.

### Events

The Agent.stream() method yields events as they occur:

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

All yielded events inherit from AgentEvent and carry `agent_id`.

### Internal tools

The agent uses a small set of internal tools for reading and writing files, executing code and commands, spawning subagents, and discovering tools:

| Tool              | Implementation                                          | Description                                                                                                                                                                                  |
| ----------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| read, write, edit | filesystem MCP server                                   | Reading, writing, and editing files via JSON tool calls (`filesystem_read_text_file`, `filesystem_read_media_file`, `filesystem_write_text_file`, `filesystem_edit_text_file`)               |
| execute           | `ipybox_execute_ipython_cell`                           | Execution of Python code and shell commands (via `!` syntax), delegated to ipybox's `CodeExecutor`, with shell commands and programmatic MCP tools calls intercepted at runtime for approval |
| subagent          | [`subagent_task`](#subagents)                           | Task delegation to child agents                                                                                                                                                              |
| tool search       | `pytools` MCP server for basic search and hybrid search | Tool discovery via category browsing or hybrid search                                                                                                                                        |

### Turn limits

Use `max_turns` to limit the number of tool-execution rounds before the stream stops:

```
async for event in agent.stream(prompt, max_turns=50):
    ...
```

If `max_turns=None` (default), the loop continues until the model produces a final response.

### Cancellation

Call cancel() to stop a running agent turn. The active `stream()` stops at the next phase boundary and yields a Cancelled event. Running kernel executions, including those in subagents, are interrupted immediately. Partial responses and synthetic tool returns are preserved in message history, so the conversation remains consistent for subsequent turns.

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

### Subagents

The built-in `subagent_task` tool delegates a subtask to a child agent with a fresh IPython kernel and fresh MCP server connections. The child inherits model, system prompt, and sandbox settings from the parent. Its events flow through the parent's stream using the same [approval](#approval) mechanism, with `agent_id` identifying the source:

```
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest(agent_id=agent_id, tool_call=tool_call) as request:
            print(f"[{agent_id}] Approve {tool_call}?")
            request.approve(True)
        case Response(content=content, agent_id=agent_id):
            print(f"[{agent_id}] {content}")
```

The main agent's `agent_id` is `main`, subagent IDs use the form `sub-xxxx`. Each delegated task defaults to `max_turns=100`. The [`max_subagents`](https://gradion-ai.github.io/freeact/configuration/#agent-settings) setting in `agent.json` limits concurrent subagents (default 5).

### Approval

The agent yields ApprovalRequest for code actions and each shell command and programmatic tool call within them. Each request carries a tool_call field identifying the pending action. Execution is suspended until `approve()` is called. Calling `approve(True)` executes the action; `approve(False)` rejects it and ends the current agent turn.

```
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

| `tool_call` type              | Trigger                                                                             |
| ----------------------------- | ----------------------------------------------------------------------------------- |
| CodeAction                    | Code action containing Python code and shell commands to execute                    |
| ShellAction                   | Shell command (`!cmd`) intercepted during code action execution                     |
| GenericCall                   | Programmatic tool call (intercepted during code action execution) or JSON tool call |
| FileRead, FileWrite, FileEdit | Filesystem operation via built-in MCP server                                        |

Shell commands and programmatic tool calls within code actions are intercepted during execution and yield separate `ApprovalRequest` events. Composite shell commands (using `&&`, `||`, `|`, `;`) are decomposed into individual sub-commands, each requiring separate approval. Python variables in shell commands are resolved before the approval request.

### Lifecycle

The agent manages MCP server connections and an IPython kernel via [ipybox](https://gradion-ai.github.io/ipybox/). On entering the async context manager, the IPython kernel starts and MCP servers configured for JSON tool calling connect. MCP servers configured for programmatic tool calling connect lazily on first tool call.

```
config = await Config.init()
async with Agent(config=config) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Without using the async context manager:

```
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

The agent supports two timeout settings in [`agent.json`](https://gradion-ai.github.io/freeact/configuration/#agent-settings):

- `execution_timeout`: Maximum time in seconds for each [code execution](https://gradion-ai.github.io/freeact/execution/index.md). Approval wait time is excluded from this budget, so the timeout only counts actual execution time. Defaults to 300 seconds. Set to `null` to disable.
- `approval_timeout`: Timeout for approval requests during programmatic tool calls. If an approval request is not accepted or rejected within this time, the tool call fails. Defaults to `null` (no timeout).

```
{
  "execution_timeout": 60,
  "approval_timeout": 30
}
```

### Persistence

#### Sessions

Config controls session persistence via `enable_persistence`.

- Default: `true`. The agent persists history to `.freeact/sessions/<session-id>/<agent-id>.jsonl`.
- `false`: The agent keeps history in memory only. Passing `session_id` to Agent raises `ValueError`.

When persistence is enabled, construct an agent without `session_id` to create a new session ID internally. Read it from `agent.session_id`:

```
# No session_id: agent creates a new session ID internally.
async with Agent(config=config) as agent:
    print(f"Generated session ID: {agent.session_id}")
    await handle_events(agent, "What is the capital of France?")
    await handle_events(agent, "What about Germany?")
```

Construct an agent with an explicit `session_id` for create-or-resume behavior:

```
# Choose an explicit session ID.
session_id = "countries-session"
# Create-or-resume behavior: resume if present, otherwise start new.
async with Agent(config=config, session_id=session_id) as agent:
    await handle_events(agent, "What is the capital of Spain?")
```

If that `session_id` already exists, the persisted history is resumed. If it does not exist, a new session starts with that ID.

To resume later, create another agent with the same `session_id`:

```
# Resume the same session ID later.
async with Agent(config=config, session_id=session_id) as agent:
    # Previous message history is restored automatically
    await handle_events(agent, "And what country did we discuss in this session?")
```

Only the main agent's message history (`main.jsonl`) is loaded on resume. Subagent messages are persisted to separate files (`sub-xxxx.jsonl`) for auditing but are not rehydrated.

The [CLI tool](https://gradion-ai.github.io/freeact/cli/index.md) accepts `--session-id` to resume a session from the command line when `enable_persistence` is `true`.

#### Results

Tool call results, code execution outputs, and subagent responses are checked against an inline size threshold before being added to the message history. When a result exceeds the threshold, the full content is saved to disk and replaced inline with a file reference notice that includes a preview. This prevents large outputs from bloating context.

Controlled by two config options:

- `tool_result_inline_max_bytes`: Maximum inline payload size in bytes.
- `tool_result_preview_chars`: Number of preview characters from both the beginning and end of large text results included in the file reference notice.

### Prompt tags

Prompts passed to `stream()` may contain skill tags that the agent processes. Skill tags explicitly invoke a skill by name. The [CLI tool](https://gradion-ai.github.io/freeact/cli/#skill-invocation) generates these from `/skill-name` syntax.

```
<skill name="review">the auth module</skill>
```

Without an explicit tag, the agent can still autonomously select a skill when the request matches a skill's description. Skills are discovered from `.freeact/skills/` and `.agents/skills/` directories.

## Permissions API

The agent does not enforce permissions itself. It yields [`ApprovalRequest`](#approval) events and leaves the decision to the application. PermissionManager is an optional utility that applications can use to automate those decisions based on stored rules. The [CLI tool](https://gradion-ai.github.io/freeact/cli/#approval-prompt) uses it internally; SDK applications can use it the same way.

The manager loads and saves rules from `.freeact/permissions.json`. Rules are glob-style [patterns](https://gradion-ai.github.io/freeact/configuration/#permissions) organized into two tiers (allow and ask) and two persistence scopes (always and session). See [Permissions](https://gradion-ai.github.io/freeact/configuration/#permissions) for the file format, pattern syntax, and matching semantics.

The core API:

- init() loads rules from `.freeact/permissions.json` if present, otherwise saves defaults.
- is_allowed(tool_call) checks a concrete tool call (literal values, no wildcards) against stored rules.
- allow_always(tool_call) adds a rule and persists it to `permissions.json`. The tool call fields may contain glob wildcards to match broadly (e.g., `command="git *"`).
- allow_session(tool_call) adds an in-memory rule for the current session. Same wildcard support as `allow_always`.

```
import asyncio
from freeact.permissions import PermissionManager
from freeact.agent import ApprovalRequest, suggest_pattern

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
