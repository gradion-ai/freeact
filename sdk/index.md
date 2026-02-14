# Agent SDK

The Agent SDK provides four main APIs:

- [Configuration API](https://gradion-ai.github.io/freeact/api/config/index.md) for initializing and loading configuration from `.freeact/`
- [Generation API](https://gradion-ai.github.io/freeact/api/generate/index.md) for generating Python APIs for MCP server tools
- [Agent API](https://gradion-ai.github.io/freeact/api/agent/index.md) for running the agentic code action loop
- [Permissions API](https://gradion-ai.github.io/freeact/api/permissions/index.md) for managing approval decisions

## Configuration API

Use Config.init() to scaffold the `.freeact/` directory from default templates. The Config() constructor loads all configuration from it:

```
from freeact.agent.config import Config

# Scaffold .freeact/ config directory if needed
await Config.init()

# Load configuration from .freeact/
config = Config()
```

See the [Configuration](https://gradion-ai.github.io/freeact/configuration/index.md) reference for details on the `.freeact/` directory structure.

## Generation API

MCP servers [configured](https://gradion-ai.github.io/freeact/configuration/#ptc-servers) as `ptc-servers` in `config.json` require Python API generation with generate_mcp_sources() before the agent can call their tools programmatically:

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
    CodeExecutionOutput,
    Response,
    Thoughts,
    ToolOutput,
)

async with Agent(config=config) as agent:
    prompt = "Who is the F1 world champion 2025?"

    async for event in agent.stream(prompt):
        match event:
            case ApprovalRequest(tool_name="ipybox_execute_ipython_cell", tool_args=args) as request:
                print(f"Code action:\n{args['code']}")
                request.approve(True)
            case ApprovalRequest(tool_name=name, tool_args=args) as request:
                print(f"Tool: {name}")
                print(f"Args: {args}")
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
| ToolOutput               | Tool or built-in operation output                 |

All yielded events inherit from AgentEvent and carry `agent_id`.

### Internal tools

The agent uses a small set of internal tools for reading and writing files, executing code and commands, spawning subagents, and discovering tools:

| Tool        | Implementation                                          | Description                                                                                        |
| ----------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| read, write | filesystem MCP server                                   | Reading and writing files via JSON tool calls                                                      |
| execute     | `ipybox_execute_ipython_cell`                           | Execution of Python code and shell commands (via `!` prefix), delegated to ipybox's `CodeExecutor` |
| subagent    | [`subagent_task`](#subagents)                           | Task delegation to child agents                                                                    |
| tool search | `pytools` MCP server for basic search and hybrid search | Tool discovery via category browsing or hybrid search                                              |

### Turn limits

Use `max_turns` to limit the number of tool-execution rounds before the stream stops:

```
async for event in agent.stream(prompt, max_turns=50):
    ...
```

If `max_turns=None` (default), the loop continues until the model produces a final response.

### Subagents

The built-in `subagent_task` tool delegates a subtask to a child agent with a fresh IPython kernel and fresh MCP server connections. The child inherits model, system prompt, and sandbox settings from the parent. Its events flow through the parent's stream using the same [approval](#approval) mechanism, with `agent_id` identifying the source:

```
async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest(agent_id=agent_id) as request:
            print(f"[{agent_id}] Approve {request.tool_name}?")
            request.approve(True)
        case Response(content=content, agent_id=agent_id):
            print(f"[{agent_id}] {content}")
```

The main agent's `agent_id` is `main`, subagent IDs use the form `sub-xxxx`. Each delegated task defaults to `max_turns=100`. The [`max-subagents`](https://gradion-ai.github.io/freeact/configuration/#agent-settings) setting in `config.json` limits concurrent subagents (default 5).

### Approval

The agent provides a unified approval mechanism. It yields ApprovalRequest for all code actions, programmatic tool calls, and JSON tool calls. Execution is suspended until `approve()` is called. Calling `approve(True)` executes the code action or tool call; `approve(False)` rejects it and ends the current agent turn.

```
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

Code action approval

For code actions, `tool_name` is `ipybox_execute_ipython_cell` and `tool_args` contains the `code` to execute.

### Lifecycle

The agent manages MCP server connections and an IPython kernel via [ipybox](https://gradion-ai.github.io/ipybox/). On entering the async context manager, the IPython kernel starts and MCP servers configured for JSON tool calling connect. MCP servers configured for programmatic tool calling connect lazily on first tool call.

```
config = Config()
async with Agent(config=config) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Without using the async context manager:

```
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

The agent supports two timeout settings in [`config.json`](https://gradion-ai.github.io/freeact/configuration/#agent-settings):

- **`execution-timeout`**: Maximum time in seconds for each [code execution](https://gradion-ai.github.io/freeact/execution/index.md). Approval wait time is excluded from this budget, so the timeout only counts actual execution time. Defaults to 300 seconds. Set to `null` to disable.
- **`approval-timeout`**: Timeout for approval requests during programmatic tool calls. If an approval request is not accepted or rejected within this time, the tool call fails. Defaults to `null` (no timeout).

```
{
  "execution-timeout": 60,
  "approval-timeout": 30
}
```

### Persistence

SessionStore persists agent message history to `.freeact/sessions/<session-uuid>/<agent-id>.jsonl`. Each agent turn appends messages incrementally, so the history is durable even if the process terminates mid-session.

```
from freeact.agent.store import SessionStore

# Create a session store with a new session ID
session_id = str(uuid.uuid4())
session_store = SessionStore(config.sessions_dir, session_id)
```

Pass the store to Agent to enable persistence.

```
# Run agent with session persistence
async with Agent(config=config, session_store=session_store) as agent:
    await handle_events(agent, "What is the capital of France?")
    await handle_events(agent, "What about Germany?")
```

To resume a session, create a new `SessionStore` with the same `session_id`. The agent loads the persisted message history on startup and continues from where it left off.

```
# Resume session with the same session ID
session_store = SessionStore(config.sessions_dir, session_id)

async with Agent(config=config, session_store=session_store) as agent:
    # Previous message history is restored automatically
    await handle_events(agent, "And what was the first country we discussed?")
```

Only the main agent's message history (`main.jsonl`) is loaded on resume. Subagent messages are persisted to separate files (`sub-xxxx.jsonl`) for auditing but are not rehydrated.

The [CLI tool](https://gradion-ai.github.io/freeact/cli/index.md) accepts `--session-id` to resume a session from the command line.

## Permissions API

Work in progress

Current permission management is preliminary and will be reimplemented in a future release.

The agent requests approval for each code action and tool call but doesn't remember past decisions. PermissionManager adds memory: `allow_always()` persists to `.freeact/permissions.json`, while `allow_session()` stores in-memory until the session ends:

```
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
