# Quickstart

This guide shows how to run your first task with freeact.

## CLI Tool

Freeact provides a [CLI tool](https://gradion-ai.github.io/freeact/cli/index.md) for running the agent in a terminal.

### Starting Freeact

Create a workspace directory, set your API key, and start the agent:

```
mkdir my-workspace && cd my-workspace
echo "GEMINI_API_KEY=your-api-key" > .env
uvx freeact
```

See [Installation](https://gradion-ai.github.io/freeact/installation/index.md) for alternative setup options and sandbox mode prerequisites.

### Generating MCP Tool APIs

On first start, the CLI tool auto-generates Python APIs for [configured](https://gradion-ai.github.io/freeact/configuration/#ptc-servers) MCP servers. For example, it creates `.freeact/generated/mcptools/google/web_search.py` for the `web_search` tool of the bundled `google` MCP server. With the generated Python API, the agent can import and call this tool programmatically.

Custom MCP servers

For calling the tools of your own MCP servers programmatically, add them to the [`ptc-servers`](https://gradion-ai.github.io/freeact/configuration/#ptc-servers) section in `.freeact/config.json`. Freeact auto-generates a Python API for them when the CLI tool starts.

### Running a Task

With this setup and a question like

> who is F1 world champion 2025?

the CLI tool should generate an output similar to the following:

The recorded session demonstrates:

- **Progressive tool loading**: The agent progressively loads tool information: lists categories, lists tools in the `google` category, then reads the `web_search` API to understand its parameters.
- **Programmatic tool calling**: The agent writes Python code that imports the `web_search` tool from `mcptools.google` and calls it programmatically with the user's query.
- **Action approval**: The code action and the programmatic `web_search` tool call are explicitly approved by the user, other tool calls were [pre-approved](https://gradion-ai.github.io/freeact/configuration/#permissions) for this example.

The code execution output shows the search result with source URLs. The agent response is a summary of it.

## Python SDK

The CLI tool is built on a [Python SDK](https://gradion-ai.github.io/freeact/sdk/index.md) that you can use directly in your applications. The following minimal example shows how to run the same task programmatically, with code actions and tool calls auto-approved:

```
import asyncio

from freeact.agent import (
    Agent,
    ApprovalRequest,
    CodeExecutionOutput,
    Response,
    Thoughts,
    ToolOutput,
)

from freeact.agent.config import Config

from freeact.agent.tools.pytools.apigen import generate_mcp_sources



async def main() -> None:
    # Scaffold .freeact/ config directory if needed
    await Config.init()

    # Load configuration from .freeact/
    config = Config()

    # Generate Python APIs for MCP servers in ptc_servers
    for server_name, params in config.ptc_servers.items():
        if not (config.generated_dir / "mcptools" / server_name).exists():
            await generate_mcp_sources({server_name: params}, config.generated_dir)

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


if __name__ == "__main__":
    asyncio.run(main())
```
