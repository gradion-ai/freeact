# Python API

The freeact CLI and terminal interface are built on a Python API that you can use directly in your applications. This guide introduces the core components and shows how to integrate freeact programmatically.

## Overview

The Python API consists of three main components:

- [`Config`][freeact.agent.config.Config] - Load and access configuration from `.freeact/`
- [`Agent`][freeact.agent.Agent] - Execute code actions and handle tool calls
- `generate_mcp_sources()` - Generate Python APIs for PTC servers

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
| [`ThoughtsChunk`][freeact.agent.ThoughtsChunk] | Partial model thinking (streaming) |
| [`Thoughts`][freeact.agent.Thoughts] | Complete model thoughts |
| [`ResponseChunk`][freeact.agent.ResponseChunk] | Partial model response (streaming) |
| [`Response`][freeact.agent.Response] | Complete model response |
| [`ApprovalRequest`][freeact.agent.ApprovalRequest] | Pending tool approval |
| [`CodeExecutionOutputChunk`][freeact.agent.CodeExecutionOutputChunk] | Partial code output (streaming) |
| [`CodeExecutionOutput`][freeact.agent.CodeExecutionOutput] | Complete code execution result |
| [`ToolOutput`][freeact.agent.ToolOutput] | JSON tool call result |

### Handling Approval Requests

Tool executions require approval. The agent yields an [`ApprovalRequest`][freeact.agent.ApprovalRequest] and suspends until you call `approve()`:

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

For automated approval, use `PermissionManager`:

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
                # Prompt user or auto-reject
                request.approve(False)
```

## Programmatic Tool Calling

For PTC servers configured in `servers.json`, generate Python APIs before starting the agent:

```python
--8<-- "examples/generate_mcptools.py:example"
```

After generation, the agent can write code that imports from `mcptools/<server>/`:

```python
from mcptools.google.search import run, Params

result = run(Params(query="python async tutorial"))
```

## Agent Lifecycle

The agent manages MCP server connections and the IPython kernel. Use it as an async context manager:

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

See [Sandboxing](features/sandbox.md) for configuration options.

## API Reference

For complete API documentation:

- [Agent API](api/agent.md) - Agent class and event types
- [Config API](api/config.md) - Configuration loading and access
