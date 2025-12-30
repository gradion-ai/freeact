# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Freeact is a code action agent library that combines an LLM with sandboxed Python code execution (via ipybox) and MCP tool integration. It supports two modes of tool calling:

- **MCP servers**: Traditional JSON-based tool calls executed directly by the agent
- **PTC servers** (Programmatic Tool Calling): Python APIs generated from MCP schemas to `mcptools/`, enabling the agent to write Python code that imports and calls tools programmatically

## Architecture

- `freeact/agent/core.py`: Main `Agent` class - LLM orchestration via pydantic-ai, streaming events, ipybox code execution, JSON and programmatic MCP tool calls, approval gating
- `freeact/agent/factory.py`: Agent creation factory with config initialization from `.freeact/`
- `freeact/agent/config/`: Unified `Config` loader - parses `.freeact/` directory (skills, prompts, server configs) into configuration objects
- `freeact/agent/tools/pytools/`: Generates Python APIs for PTC servers. Tool category discovery from `mcptools/`
- `freeact/terminal/interface.py`: `Terminal` class - conversation loop, event streaming, approval handling via `PermissionManager`
- `freeact/terminal/display.py`: Rich-based rendering with prompt_toolkit
- `freeact/permissions.py`: Tool permission management (always/session-based), persists to `.freeact/permissions.json`

### Server Configuration

Both server types are configured in `.freeact/servers.json`:

- **mcp-servers**: Agent calls these directly via JSON tool calls
- **ptc-servers**: Python APIs generated to `mcptools/<server_name>/` at startup; agent writes code that imports and uses these typed APIs

### Approval Flow

All tool executions require approval. `Agent.stream()` yields `ApprovalRequest` before executing any tool:

- **JSON tool calls** (MCP servers, ipybox tools): `ApprovalRequest` yielded in `_execute_tool()` before execution
- **PTC tool calls**: When executed code calls a tool, ipybox yields `ipybox.ApprovalRequest` which freeact wraps in its own `ApprovalRequest` and surfaces to the caller

The `Terminal` uses `PermissionManager` to handle approvals with always/session/once modes.
