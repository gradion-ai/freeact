# Python SDK

The freeact [CLI and terminal interface](cli.md) are built on a Python SDK that you can use directly in your applications.

## Overview

The Python SDK provides three main components:

- [`Config`][freeact.agent.config.Config] - Loads and provides access to configuration from `.freeact/`
- [`Agent`][freeact.agent.Agent] - Orchestrates code execution and MCP tool calls
- [`generate_mcp_sources()`][freeact.agent.tools.pytools.apigen.generate_mcp_sources] - Generates Python APIs for [configured](configuration.md#mcp-server-configuration) MCP servers

## Config

The [`Config`][freeact.agent.config.Config] class loads all configuration from `.freeact/` on instantiation.

### Initialization

The [`init_config()`][freeact.agent.config.init_config] function initializes the `.freeact/` directory from default templates:

```python
--8<-- "examples/custom_config.py:config"
```

### Accessing Configuration

The loaded configuration provides access to model settings, system prompt, skills metadata, and server configurations:

```python
--8<-- "examples/custom_config.py:access"
```

See the [Configuration](configuration.md) reference for details on the `.freeact/` directory structure.

## Agent

The [`Agent`][freeact.agent.Agent] class orchestrates code execution and tool calling. It manages an IPython kernel, MCP server connections, and conversation history.

### Basic Usage

```python
--8<-- "examples/basic_agent.py:example"
```

### Events

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
| [`ToolOutput`][freeact.agent.ToolOutput] | JSON tool call output |

### Approval

Code actions, JSON tool calls, and programmatic tool calls all require approval. The agent yields an [`ApprovalRequest`][freeact.agent.ApprovalRequest] and suspends until `approve()` is called:

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

### Permissions

The agent yields approval requests without managing permissions. The terminal interface uses [`PermissionManager`][freeact.permissions.PermissionManager] to implement `Y/n/a/s` approval choices, where `a` (always) persists permissions to disk and `s` (session) grants approval for the current session:

```python
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

### Lifecycle

The agent manages MCP server connections and an IPython kernel. On entering the async context manager, the IPython kernel starts and MCP servers configured for JSON tool calls connect. MCP servers configured for programmatic tool calling connect lazily on first tool call.

```python
async with Agent(...) as agent:
    async for event in agent.stream(prompt):
        ...
# Connections closed, kernel stopped
```

Explicit lifecycle management is also supported:

```python
agent = Agent(...)
await agent.start()
try:
    async for event in agent.stream(prompt):
        ...
finally:
    await agent.stop()
```

## API generation

MCP servers [configured](configuration.md#mcp-server-configuration) as `ptc-servers` in `servers.json` require Python API generation before the agent can call them programmatically:

```python
--8<-- "examples/generate_mcptools.py:example"
```

API generation runs once per server configuration. The generated modules persist in `mcptools/` across agent sessions. After generation, the agent can import them from `mcptools/<server>/`:

```python
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
```

## SDK Reference

- [Agent API](api/agent.md) - Agent class and event types
- [Config API](api/config.md) - Configuration loading and access
- [Generate API](api/generate.md) - MCP source generation
- [Permissions API](api/permissions.md) - Permission management
