# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Freeact is a lightweight, general-purpose agent that acts via [code actions](https://machinelearning.apple.com/research/codeact) rather than JSON tool calls. It writes executable Python code that can call multiple tools programmatically, process intermediate results, and use loops and conditionals in a single pass - tasks that would otherwise require many inference rounds with JSON tool calling.

Beyond executing tools, freeact can develop new tools from successful code actions, evolving its own tool library over time. Tools are defined via Python interfaces, progressively discovered and loaded from the agent's workspace rather than consuming context upfront. All execution happens locally in a secure sandbox via [ipybox](https://gradion-ai.github.io/ipybox/).

Key capabilities:
- **Programmatic tool calling**: Generates typed Python APIs from MCP tool schemas to `mcptools/`, enabling tool calls within code actions
- **Reusable code actions**: Successful code actions can be saved as discoverable tools in `gentools/` with clean interfaces
- **Agent skills**: Supports the [agentskills.io](https://agentskills.io/) specification for extending agent capabilities with specialized knowledge and workflows
- **Progressive loading**: Tool/skill information loads in stages as needed, not upfront
- **Unified approval**: Code actions, programmatic tool calls, and JSON-based tool calls all require approval before proceeding

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

**Note:** `invoke cc` only checks files under version control. Run `git add` on new files first.

## Architecture

### Core Components

- `freeact/agent/core.py`: Main `Agent` class - pydantic-ai orchestration, streaming events, ipybox code execution, approval gating. Yields event types: `ResponseChunk`, `Response`, `ApprovalRequest`, `CodeExecutionOutput`, `ToolOutput`, etc.
- `freeact/agent/config/config.py`: `Config` class - loads `.freeact/` directory (skills metadata, system prompt, server configs)
- `freeact/agent/config/init.py`: Initializes `.freeact/` from templates on first run
- `freeact/agent/tools/pytools/apigen.py`: Generates Python APIs for PTC servers using `ipybox.generate_mcp_sources()`
- `freeact/agent/tools/pytools/categories.py`: Discovers tool categories from `gentools/` and `mcptools/`
- `freeact/media/`: Reusable media handling - `parse_prompt()` for `@file` reference extraction, image loading/downscaling
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

### Tool Search System

Two tool discovery modes, configured via CLI `--tool-search {basic|hybrid}`:

- **basic**: List-based search via `freeact/agent/tools/pytools/search/basic.py` - provides `list_categories` and `list_tools` MCP tools for manual category/tool browsing
- **hybrid**: BM25 + vector search via `freeact/agent/tools/pytools/search/hybrid/` - provides `search_tools` MCP tool for natural language queries

Hybrid search components (`search/hybrid/`):
- `database.py`: SQLite with sqlite-vec extension for vector storage
- `embed.py`: Query/document embedding via pydantic-ai embeddings
- `extract.py`: Parses tool metadata from `api.py` files (docstrings, signatures)
- `index.py`: Builds and syncs the search index from `gentools/` and `mcptools/`
- `search.py`: BM25, vector, and hybrid search implementations
- `server.py`: FastMCP server exposing `search_tools` tool
- `watch.py`: File system watcher for automatic index updates

The hybrid server runs as an MCP server and can be started with:
```bash
python -m freeact.agent.tools.pytools.search.hybrid
```

### Approval Flow

All tool executions require approval. `Agent.stream()` yields `ApprovalRequest` before executing any tool:

- **JSON tool calls** (MCP servers, ipybox tools): `ApprovalRequest` yielded in `_execute_tool()` before execution
- **PTC tool calls**: When executed code calls a tool, ipybox yields `ipybox.ApprovalRequest` which freeact wraps in its own `ApprovalRequest` and surfaces to the caller

The `Terminal` uses `PermissionManager` to handle approvals with always/session/once modes.
