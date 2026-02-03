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

The Agent class implements the agentic code action loop, handling code action generation, code execution, tool calls, and the approval workflow. Each stream() call runs a single agent turn, with the agent managing conversation history across calls. Use `stream()` to iterate over [events](#events) and handle them with pattern matching:

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
    model=config.model,
    model_settings=config.model_settings,
    system_prompt=config.system_prompt,
    mcp_servers=config.mcp_servers,
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
| ToolOutput               | JSON tool call output                             |

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
async with Agent(...) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Without using the async context manager:

```
agent = Agent(...)
await agent.start()
try:
    async for event in agent.stream(prompt):
        ...
finally:
    await agent.stop()
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
