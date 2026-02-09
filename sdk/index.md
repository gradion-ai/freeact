# Python SDK

The Python SDK provides four main APIs:

- [Configuration API](https://gradion-ai.github.io/freeact/api/config/index.md) for initializing and loading configuration from `.freeact/`
- [Generation API](https://gradion-ai.github.io/freeact/api/generate/index.md) for generating Python APIs for MCP server tools
- [Agent API](https://gradion-ai.github.io/freeact/api/agent/index.md) for running the agentic code action loop
- [Permissions API](https://gradion-ai.github.io/freeact/api/permissions/index.md) for managing approval decisions

## Configuration API

Use init_config() to initialize the `.freeact/` directory from default templates. The optional `tool_search` parameter selects the tool discovery mode (`"basic"` or `"hybrid"`). The Config() constructor loads all configuration from it:

```
from freeact.agent.config import Config, init_config

# Initialize .freeact/ config directory if needed
init_config()

# Load configuration from .freeact/
config = Config()
```

See the [Configuration](https://gradion-ai.github.io/freeact/configuration/index.md) reference for details on the `.freeact/` directory structure.

## Generation API

MCP servers [configured](https://gradion-ai.github.io/freeact/configuration/#mcp-servers) as `ptc-servers` in `servers.json` require Python API generation with generate_mcp_sources() before the agent can call their tools programmatically:

```
from freeact.agent.tools.pytools.apigen import generate_mcp_sources

# Generate Python APIs for MCP servers in ptc_servers
for server_name, params in config.ptc_servers.items():
    if not Path(f"mcptools/{server_name}").exists():
        await generate_mcp_sources({server_name: params})
```

Generated APIs are stored as `mcptools/<server_name>/<tool>.py` modules and persist across agent sessions. After generation, the agent can import them for programmatic tool calling:

```
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
```

## Agent API

The Agent class implements the agentic code action loop, handling code action generation, code execution, tool calls, and the approval workflow. The constructor requires an agent ID as the first argument (for example `"main"` in apps using a single top-level agent). Each stream() call runs a single agent turn, with the agent managing conversation history across calls. Use `stream()` to iterate over [events](#events) and handle them with pattern matching:

```
from freeact.agent import (
    Agent,
    ApprovalRequest,
    CodeExecutionOutput,
    Response,
    Thoughts,
    ToolOutput,
)

async with Agent(
    "main",
    model=config.model,
    model_settings=config.model_settings,
    system_prompt=config.system_prompt,
    mcp_server_factory=config.create_mcp_servers,
) as agent:
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

Subagent IDs use the form `sub-xxxx`. Each delegated task defaults to `max_turns=100`. Use `max_subagents` on the parent to limit concurrent subagents (default 5).

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

The agent manages MCP server connections and an IPython kernel via [ipybox](https://gradion-ai.github.io/ipybox/). On entering the async context manager, the IPython kernel starts and MCP servers configured for JSON tool calling connect. MCP servers configured for programmatic tool calling connect lazily on first tool call. When constructing agents directly, pass `mcp_server_factory` (a callable returning fresh MCP server instances) rather than pre-instantiated server objects.

```
async with Agent("main", ...) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Without using the async context manager:

```
agent = Agent("main", ...)
await agent.start()
try:
    async for event in agent.stream(prompt):
        ...
finally:
    await agent.stop()
```

### Timeouts

The agent supports two timeout configurations:

- **execution_timeout**: Maximum time in seconds for each code execution. Approval wait time is excluded from this budget, so the timeout only counts actual execution time. Defaults to 300 seconds. Set to `None` to disable.
- **approval_timeout**: Timeout for approval requests during programmatic tool calls. If an approval request is not accepted or rejected within this time, the tool call fails. Defaults to `None` (no timeout).

```
agent = Agent(
    "main",
    model="anthropic:claude-sonnet-4-20250514",
    model_settings=model_settings,
    system_prompt=config.system_prompt,
    execution_timeout=60,     # 60 second execution limit (excludes approval wait)
    approval_timeout=30,      # 30 second approval limit
)
```

## Permissions API

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
