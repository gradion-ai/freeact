# First agent with the SDK

The [CLI tool](../reference/cli.md) is built on the Agent SDK that you can use directly in your applications. This tutorial builds a minimal application that runs the same task as the [CLI quickstart](quickstart.md) programmatically: load and resolve configuration, generate MCP tool APIs, run the agent, and handle its events, with code actions and tool calls auto-approved by the application.

The complete example is [`examples/basic_agent.py`](https://github.com/gradion-ai/freeact/blob/main/examples/basic_agent.py), shown in full at the [end of this tutorial](#complete-example).

## 1. Set up a workspace

Create a workspace directory with freeact [installed](installation.md) and set your API key:

```bash
mkdir my-workspace && cd my-workspace
uv init --bare --python 3.13
uv add freeact
export GEMINI_API_KEY="your-api-key"
```

!!! note "`.env` loading"

    Automatic `.env` loading is a [CLI feature](../reference/cli.md). SDK applications read configuration from the process environment; export the API key or load a `.env` file yourself.

## 2. Load and resolve configuration

Configuration flows one way: file, then schema, then resolution. [`config.init()`][freeact.config.init] sets up the `.freeact/` workspace (writes the commented default `config.toml` when missing, creates runtime directories, materializes bundled skills). [`config.resolve()`][freeact.config.resolve] turns a parsed [`FreeactConfig`][freeact.config.FreeactConfig] into a [`ResolvedRuntime`][freeact.config.ResolvedRuntime]: it expands tool presets into server configs, substitutes `${VAR}` references, and prepares the model for pydantic-ai.

```python
--8<-- "examples/basic_agent.py:config-imports"
--8<-- "examples/basic_agent.py:config"
```

This example enables the `search` and `fetch` presets in code. In a real workspace, set them in `.freeact/config.toml` and load the file with [`config.load()`][freeact.config.load] instead:

```python
runtime = config.resolve(config.load())
```

There is no programmatic save: freeact writes `config.toml` only at `init` and never rewrites it. Edit the file to change configuration. See the [Configuration](../reference/configuration.md) reference for the file format and the `.freeact/` directory structure.

## 3. Generate MCP tool APIs

MCP servers configured as [`ptc_servers`](../guides/tool-servers.md#add-servers-for-programmatic-tool-calling) require Python API generation with [`generate_mcp_sources()`][freeact.tools.pytools.apigen.generate_mcp_sources] before the agent can call their tools programmatically. The CLI tool does this automatically on start; SDK applications call it explicitly:

```python
--8<-- "examples/basic_agent.py:apigen-imports"
--8<-- "examples/basic_agent.py:apigen"
```

Generated APIs are stored as `.freeact/generated/mcptools/<server_name>/<tool>.py` modules and persist across agent sessions. The `.freeact/generated/` directory is on the kernel's `PYTHONPATH`, so the agent can import them directly in code actions:

```python
from mcptools.google.web_search import run, Params

result = run(Params(query="python async tutorial"))
```

## 4. Run the agent and handle events

The [`Agent`][freeact.Agent] class implements the agentic code action loop, handling code action generation, code execution, tool calls, and the approval workflow. Each [`stream()`][freeact.Agent.stream] call runs a single agent turn, with the agent managing conversation history across calls. Iterate over the yielded events and handle them with pattern matching:

```python
--8<-- "examples/basic_agent.py:agent"
```

Three things to note:

- The `async with` block starts the IPython kernel and MCP server connections on entry and closes them on exit.
- Every [`ApprovalRequest`][freeact.ApprovalRequest] suspends execution until the application calls `approve()`. This example approves everything with `approve(True)`; `approve(False)` rejects the action and ends the current agent turn.
- [`Thoughts`][freeact.Thoughts], [`CodeExecutionOutput`][freeact.CodeExecutionOutput], [`ToolOutput`][freeact.ToolOutput], and [`Response`][freeact.Response] are complete events. For processing output incrementally, match their `*Chunk` variants instead. See [Runtime model](../concepts/runtime.md) for the full event list.

## 5. Run the application

Save the complete example as `basic_agent.py` and run it:

```bash
uv run python basic_agent.py
```

The output shows the agent's thoughts, the code action importing and calling `web_search` from `mcptools.google`, the execution output with search results, and the final response.

## Complete example

```python
--8<-- "examples/basic_agent.py"
```

## Next steps

- Understand the event stream, turns, and cancellation: [Runtime model](../concepts/runtime.md)
- Persist conversations and resume them later: [Persist and resume sessions](../guides/sessions.md)
- Replace blanket auto-approval with stored permission rules: [Manage permissions](../guides/permissions.md)
- Full API documentation: [Agent](../api/agent.md), [Config](../api/config.md), [Generate](../api/generate.md), [Permissions](../api/permissions.md)
