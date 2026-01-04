# Quickstart

This guide shows how to run your first task with freeact.

## CLI Tool

Freeact provides a [CLI tool](cli.md) for running the agent in a terminal. 

### Starting Freeact

Create a workspace directory, set your API key, and start the agent:

```bash
mkdir my-workspace && cd my-workspace
echo "GEMINI_API_KEY=your-api-key" > .env
uvx freeact
```

See [Installation](installation.md) for alternative setup options and sandbox prerequisites.

### Generating MCP Tool APIs

On first start, the CLI tool auto-generates Python APIs for tools of [configured](configuration.md#ptc-servers) MCP servers. For example, it creates `mcptools/google/web_search.py` for the `web_search` tool of the bundled `google` MCP server. With the generated Python API, the agent can import and call this tool programmatically. 

!!! tip "Custom MCP servers"

    For calling the tools of your own MCP servers programmatically, add them to the `ptc-servers` section in `.freeact/servers.json`. Freeact auto-generates a Python API for them when the CLI tool starts.

### Running a Task

With this setup and a question like 

> who is F1 world champion 2025? 

the CLI tool should generate an output similar to the following:

[![Terminal session](recordings/quickstart/conversation.svg)](recordings/quickstart/conversation.html){target="_blank"}

The recorded session demonstrates:

- **Progressive tool loading**: The agent progressively loads tool information: lists categories, lists tools in the `google` category, then reads the `web_search` API to understand its parameters.
- **Programmatic tool calling**: The agent writes Python code that imports the `web_search` tool from `mcptools.google` and calls it programmatically with the user's query.
- **Action approval**: The code action and the programmatic `web_search` tool call were explicitly approved by the user, other tool calls were [pre-approved](configuration.md#permissions) for this example.

The code execution output shows the search result with source URLs. The agent response is a summary of it.

## Python SDK

The CLI tool uses the freeact [Python SDK](python-sdk.md) internally. Here's a minimal example that runs the same task programmatically:

```python
--8<-- "examples/basic_agent.py:example"
```

### Output Content Streaming

You can also handle output content streams by matching `ResponseChunk`, `ThoughtsChunk`, and `CodeExecutionOutputChunk`. These events provide output increments as they are generated. See [`Agent.stream()`][freeact.agent.Agent.stream] for details.

### Unified Approval Mechanism

The agent provides a unified approval mechanism. It yields [`ApprovalRequest`][freeact.agent.ApprovalRequest] for all code actions, programmatic tool calls, and JSON tool calls. Execution is suspended until `approve()` is called.

Saving approval decisions is handled by a [`PermissionManager`][freeact.permissions.PermissionManager] that is integrated into the CLI tool but skipped in this code example for brevity. The agent itself does not save approval decisions.

### SDK Reference

- [Agent API](api/agent.md) - Agent class and event types
- [Config API](api/config.md) - Configuration loading and access
- [Generate API](api/generate.md) - MCP source generation
- [Permissions API](api/permissions.md) - Permission management
