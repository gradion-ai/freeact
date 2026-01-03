# Python SDK

The freeact [CLI and terminal interface](cli.md) are built on a Python SDK that you can use directly in your applications. This guide introduces the core components and shows how to integrate freeact programmatically.

## Overview

The Python SDK consists of three main components:

- [`Config`][freeact.agent.config.Config] - Load and access configuration from `.freeact/`
- [`Agent`][freeact.agent.Agent] - Generate and execute code actions, call MCP tools
- [`generate_mcp_sources()`][freeact.agent.tools.pytools.apigen.generate_mcp_sources] - Generate Python APIs for [configured](configuration.md#mcp-server-configuration) MCP servers

## Basic Usage

The simplest way to use the agent:

```python
--8<-- "examples/basic_agent.py:example"
```

## Configuration

The [`Config`][freeact.agent.config.Config] class loads all configuration from `.freeact/` on instantiation:

```python
--8<-- "examples/custom_config.py:config"
```

### Accessing Configuration

After loading, you can access:

```python
--8<-- "examples/custom_config.py:access"
```

See the [Configuration](configuration.md) reference for details on the `.freeact/` directory structure.

## Agent Events

The [`Agent.stream()`][freeact.agent.Agent.stream] method yields events as they occur:

| Event | Description |
|-------|-------------|
| [`ThoughtsChunk`][freeact.agent.ThoughtsChunk] | Partial model thinking (content streaming) |
| [`Thoughts`][freeact.agent.Thoughts] | Complete model thoughts at a given step |
| [`ResponseChunk`][freeact.agent.ResponseChunk] | Partial model response (content streaming) |
| [`Response`][freeact.agent.Response] | Complete model response |
| [`ApprovalRequest`][freeact.agent.ApprovalRequest] | Pending code action or tool call approval |
| [`CodeExecutionOutputChunk`][freeact.agent.CodeExecutionOutputChunk] | Partial code execution output (content streaming) |
| [`CodeExecutionOutput`][freeact.agent.CodeExecutionOutput] | Complete code execution output |
| [`ToolOutput`][freeact.agent.ToolOutput] | JSON tool call result |

### Handling Approval Requests

Code actions, JSON tool calls, and programmatic tool calls all require approval. The agent provides a unified approval mechanism: regardless of the action type, it yields an [`ApprovalRequest`][freeact.agent.ApprovalRequest] and suspends until you call `approve()`:

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

The agent only yields approval requests without managing permissions. The terminal interface uses [`PermissionManager`][freeact.permissions.PermissionManager] to handle `Y/n/a/s` approval choices, where `a` (always) persists permissions to disk and `s` (session) grants approval for the current session. Minimal usage:

```python
from freeact.permissions import PermissionManager

manager = PermissionManager()
await manager.load()

async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest() as request:
            if manager.is_allowed(request.tool_name, request.tool_args):
                request.approve(True)
            else:
                choice = input("Allow? [Y/n/a/s]: ")  # prompt user
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

## Programmatic Tool Calling

For MCP servers [configured](configuration.md#mcp-server-configuration) as `ptc-servers` in the `servers.json` file, generate Python APIs for their tools before starting the agent:

```python
--8<-- "examples/generate_mcptools.py:example"
```

API generation only needs to run once per server configuration. The generated modules are written to `mcptools/` and persist across agent sessions. After generation, the agent can write code that imports from `mcptools/<server>/`:

```python
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
```

## Agent Lifecycle

The agent manages MCP server connections and the IPython kernel. On entering the async context manager, the IPython kernel starts and MCP servers configured for JSON tool calls connect. MCP servers configured for [programmatic tool calling](#programmatic-tool-calling) connect lazily on first tool call. Use the agent as an async context manager:

```python
async with Agent(...) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Or manage the lifecycle explicitly:

```python
agent = Agent(...)
await agent.start()
try:
    async for event in agent.stream(prompt):
        ...
finally:
    await agent.stop()
```

## Sandbox Mode

Enable sandboxed code execution with configurable restrictions:

```python
from pathlib import Path

agent = Agent(
    model=config.model,
    model_settings=config.model_settings,
    system_prompt=config.system_prompt,
    mcp_servers=config.mcp_servers,
    sandbox=True,
    sandbox_config=Path("sandbox-config.json"),
)
```

If `sandbox_config` is omitted, the agent runs with the default sandbox configuration:

- **Filesystem**: Read all files except `.env`, write to current directory and subdirectories
- **Network**: Internet access blocked, local network access to tool execution server permitted

See [Sandboxing](features/sandbox.md) for custom configuration options.

## API Reference

For complete API documentation:

- [Agent API](api/agent.md) - Agent class and event types
- [Config API](api/config.md) - Configuration loading and access
- [Generate API](api/generate.md) - MCP source generation
- [Permissions API](api/permissions.md) - Permission management
