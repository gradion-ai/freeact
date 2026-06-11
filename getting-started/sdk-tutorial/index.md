# First agent with the SDK

The [CLI tool](https://gradion-ai.github.io/freeact/reference/cli/index.md) is built on the Agent SDK that you can use directly in your applications. This tutorial builds a minimal application that runs the same task as the [CLI quickstart](https://gradion-ai.github.io/freeact/getting-started/quickstart/index.md) programmatically: load and resolve configuration, generate MCP tool APIs, run the agent, and handle its events, with code actions and tool calls auto-approved by the application.

The complete example is [`examples/basic_agent.py`](https://github.com/gradion-ai/freeact/blob/main/examples/basic_agent.py), shown in full at the [end of this tutorial](#complete-example).

## 1. Set up a workspace

Create a workspace directory with freeact [installed](https://gradion-ai.github.io/freeact/getting-started/installation/index.md) and set your API key:

```
mkdir my-workspace && cd my-workspace
uv init --bare --python 3.13
uv add freeact
export GEMINI_API_KEY="your-api-key"
```

`.env` loading

Automatic `.env` loading is a [CLI feature](https://gradion-ai.github.io/freeact/reference/cli/index.md). SDK applications read configuration from the process environment; export the API key or load a `.env` file yourself.

## 2. Load and resolve configuration

Configuration flows one way: file, then schema, then resolution. config.init() sets up the `.freeact/` workspace (writes the commented default `config.toml` when missing, creates runtime directories, materializes bundled skills). config.resolve() turns a parsed FreeactConfig into a ResolvedRuntime: it expands tool presets into server configs, substitutes `${VAR}` references, and prepares the model for pydantic-ai.

```
from freeact import (
    Agent,
    ApprovalRequest,
    CodeAction,
    CodeExecutionOutput,
    Response,
    ShellAction,
    Thoughts,
    ToolOutput,
    config,
)

config.init()  # set up the .freeact/ workspace (config.toml, dirs, bundled skills)

# Enable the bundled search and fetch tool servers for this example
# (in a real workspace, set them in .freeact/config.toml instead).
cfg = config.FreeactConfig.model_validate({"agent": {"tools": {"search": True, "fetch": True}}})
runtime = config.resolve(cfg)
```

This example enables the `search` and `fetch` presets in code. In a real workspace, set them in `.freeact/config.toml` and load the file with config.load() instead:

```
runtime = config.resolve(config.load())
```

There is no programmatic save: freeact writes `config.toml` only at `init` and never rewrites it. Edit the file to change configuration. See the [Configuration](https://gradion-ai.github.io/freeact/reference/configuration/index.md) reference for the file format and the `.freeact/` directory structure.

## 3. Generate MCP tool APIs

MCP servers configured as [`ptc_servers`](https://gradion-ai.github.io/freeact/guides/tool-servers/#add-servers-for-programmatic-tool-calling) require Python API generation with generate_mcp_sources() before the agent can call their tools programmatically. The CLI tool does this automatically on start; SDK applications call it explicitly:

```
from freeact.tools.pytools.apigen import generate_mcp_sources

# Generate Python APIs for MCP servers in ptc_servers
generated_dir = runtime.workspace.generated_dir
for server_name, params in runtime.ptc_servers.items():
    if not (generated_dir / "mcptools" / server_name).exists():
        await generate_mcp_sources({server_name: params}, generated_dir)
```

Generated APIs are stored as `.freeact/generated/mcptools/<server_name>/<tool>.py` modules and persist across agent sessions. The `.freeact/generated/` directory is on the kernel's `PYTHONPATH`, so the agent can import them directly in code actions:

```
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
```

## 4. Run the agent and handle events

The Agent class implements the agentic code action loop, handling code action generation, code execution, tool calls, and the approval workflow. Each stream() call runs a single agent turn, with the agent managing conversation history across calls. Iterate over the yielded events and handle them with pattern matching:

```
async with Agent(runtime) as agent:
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

Three things to note:

- The `async with` block starts the IPython kernel and MCP server connections on entry and closes them on exit.
- Every ApprovalRequest suspends execution until the application calls `approve()`. This example approves everything with `approve(True)`; `approve(False)` rejects the action and ends the current agent turn.
- Thoughts, CodeExecutionOutput, ToolOutput, and Response are complete events. For processing output incrementally, match their `*Chunk` variants instead. See [Runtime model](https://gradion-ai.github.io/freeact/concepts/runtime/index.md) for the full event list.

## 5. Run the application

Save the complete example as `basic_agent.py` and run it:

```
uv run python basic_agent.py
```

The output shows the agent's thoughts, the code action importing and calling `web_search` from `mcptools.google`, the execution output with search results, and the final response.

## Complete example

```
import asyncio

from freeact import (
    Agent,
    ApprovalRequest,
    CodeAction,
    CodeExecutionOutput,
    Response,
    ShellAction,
    Thoughts,
    ToolOutput,
    config,
)

from freeact.tools.pytools.apigen import generate_mcp_sources



async def main() -> None:
    config.init()  # set up the .freeact/ workspace (config.toml, dirs, bundled skills)

    # Enable the bundled search and fetch tool servers for this example
    # (in a real workspace, set them in .freeact/config.toml instead).
    cfg = config.FreeactConfig.model_validate({"agent": {"tools": {"search": True, "fetch": True}}})
    runtime = config.resolve(cfg)

    # Generate Python APIs for MCP servers in ptc_servers
    generated_dir = runtime.workspace.generated_dir
    for server_name, params in runtime.ptc_servers.items():
        if not (generated_dir / "mcptools" / server_name).exists():
            await generate_mcp_sources({server_name: params}, generated_dir)

    async with Agent(runtime) as agent:
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


if __name__ == "__main__":
    asyncio.run(main())
```

## Next steps

- Understand the event stream, turns, and cancellation: [Runtime model](https://gradion-ai.github.io/freeact/concepts/runtime/index.md)
- Persist conversations and resume them later: [Persist and resume sessions](https://gradion-ai.github.io/freeact/guides/sessions/index.md)
- Replace blanket auto-approval with stored permission rules: [Manage permissions](https://gradion-ai.github.io/freeact/guides/permissions/index.md)
- Full API documentation: [Agent](https://gradion-ai.github.io/freeact/api/agent/index.md), [Config](https://gradion-ai.github.io/freeact/api/config/index.md), [Generate](https://gradion-ai.github.io/freeact/api/generate/index.md), [Permissions](https://gradion-ai.github.io/freeact/api/permissions/index.md)
