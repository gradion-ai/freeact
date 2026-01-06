# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Freeact is a code action agent that acts via Python code execution rather than JSON tool calls. The agent writes executable Python code that calls multiple tools, processes intermediate results, and branches on conditions. Tasks that would require many inference rounds with JSON tool calling can be completed in a single pass. Code executes in a sandboxed IPython kernel via [ipybox](https://gradion-ai.github.io/ipybox/).

Key capabilities:
- **Programmatic Tool Calling (PTC)**: Auto-generates typed Python modules from MCP tool schemas to `mcptools/`, enabling tool calls within code actions
- **Reusable code actions**: Successful code actions can be saved as discoverable tools in `gentools/`
- **Agent skills**: Filesystem-based capability packages in `.freeact/skills/` that extend agent behavior
- **Progressive disclosure**: Tool/skill information loads in stages as needed, not upfront

## Development Commands

```bash
uv sync                      # Install dependencies
uv run invoke cc             # Run code checks (auto-fixes formatting, mypy errors need manual fix)
uv run invoke test           # Run all tests
uv run invoke ut             # Run unit tests only
uv run invoke it             # Run integration tests only
uv run invoke test --cov     # Run tests with coverage

# Single test file
uv run pytest -xsv tests/integration/test_agent.py

# Single test
uv run pytest -xsv tests/integration/test_agent.py::test_name

# Documentation
uv run invoke build-docs     # Build docs
uv run invoke serve-docs     # Serve docs at localhost:8000
```

## Architecture

### Core Components

- `freeact/agent/core.py`: Main `Agent` class - pydantic-ai orchestration, streaming events, ipybox code execution, approval gating. Yields event types: `ResponseChunk`, `Response`, `ApprovalRequest`, `CodeExecutionOutput`, `ToolOutput`, etc.
- `freeact/agent/config/config.py`: `Config` class - loads `.freeact/` directory (skills metadata, system prompt, server configs)
- `freeact/agent/config/init.py`: Initializes `.freeact/` from templates on first run
- `freeact/agent/tools/pytools/apigen.py`: Generates Python APIs for PTC servers using `ipybox.generate_mcp_sources()`
- `freeact/agent/tools/pytools/categories.py`: Discovers tool categories from `gentools/` and `mcptools/`
- `freeact/terminal/interface.py`: `Terminal` class - conversation loop, event rendering, approval handling
- `freeact/permissions.py`: `PermissionManager` - two-tier approval (always/session), persists to `.freeact/permissions.json`
- `freeact/cli.py`: CLI entry point, loads config, creates agent, runs terminal

### Configuration Directory (`.freeact/`)

- `prompts/system.md`: System prompt template with `{working_dir}` and `{skills}` placeholders
- `servers.json`: Server configuration with `mcp-servers` (JSON tool calls) and `ptc-servers` (code-based calls)
- `skills/*`: Agent skill directories
- `plans/`: Task plan storage
- `permissions.json`: Persisted tool permissions

### Tool Directories

- `mcptools/<server>/`: Auto-generated Python APIs from PTC server schemas
- `gentools/<category>/<tool>/api.py`: Python APIs of code actions saved as tools

### Server Configuration

Both server types are configured in `.freeact/servers.json`:

- **mcp-servers**: Agent calls these directly via JSON tool calls
- **ptc-servers**: Python APIs generated to `mcptools/<server_name>/` at startup; agent writes code that imports and uses these typed APIs

### Approval Flow

All tool executions require approval. `Agent.stream()` yields `ApprovalRequest` before executing any tool:

- **JSON tool calls** (MCP servers, ipybox tools): `ApprovalRequest` yielded in `_execute_tool()` before execution
- **PTC tool calls**: When executed code calls a tool, ipybox yields `ipybox.ApprovalRequest` which freeact wraps in its own `ApprovalRequest` and surfaces to the caller

The `Terminal` uses `PermissionManager` to handle approvals with always/session/once modes.
