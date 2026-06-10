# Module Boundary Constraints

## Dependency direction

```
cli.py -> config, agent, permissions, terminal, tools/pytools/apigen   (cli wires everything)

terminal/  -> events, toolcalls, permissions, config
agent/     -> events, toolcalls, config
permissions.py -> toolcalls
events.py  -> toolcalls (ApprovalRequest carries a ToolCall)
toolcalls.py -> nothing internal
config/    -> nothing internal (imports only within config/)
tools/     -> nothing internal except tools/security.py (fetch, bsearch);
              tools are subprocess MCP entry points and never import agent/terminal
```

Hard rules:

- `agent/` NEVER imports `terminal` or `permissions`. The SDK stays policy-free: `Agent` emits `ApprovalRequest`s; the embedder (terminal or any other consumer) decides approvals.
- `Phase` lives in `freeact/events.py` so the terminal can read `Cancelled.phase` without importing `agent/`.
- Shell PATTERN suggestion (`suggest_shell_pattern`) lives in `freeact/toolcalls.py` with the rest of the pattern symmetry methods; shell SPLITTING (`split_composite_command`) lives in `freeact/agent/shell.py`. The terminal only ever needs patterns, never splitting.
- `freeact/terminal/` must not import `pydantic_ai`. Model-level types stay inside `agent/`; `events.py` re-exposes only what the event surface needs (`ToolResult` in `ToolOutput`).
- Built-in (non-MCP) tool definitions are JSON data files under `freeact/agent/tooldefs/` with their loader (`load.py`); used by the executor (ipybox tools, subagent task tool).
- `.env` autoload and logging setup happen in `cli.py` only.

## Package `__init__.py` files are re-exports only

No function or class definitions in `__init__.py`. They contain only imports from submodules and an `__all__` list. No module-level docstrings.

- `freeact/__init__.py`: public SDK surface (Agent, events, toolcalls, PermissionManager, pattern helpers).
- `freeact/agent/__init__.py`: re-exports from `agent`, `approvals`, `executor`, `mcp`, `session`, `shell`, `subagents`.
- `freeact/config/__init__.py`: re-exports from `load`, `resolve`, `schema`, `skills`.
- `freeact/terminal/__init__.py`: re-exports from `app`, `approvals`, `clipboard`, `dispatcher`, `screens`, `view`, `widgets`.
- `freeact/agent/tooldefs/__init__.py`: re-exports from `load`.
- `freeact/tools/__init__.py`: empty. `freeact/tools/filesystem/__init__.py` re-exports from `processing`; `freeact/tools/pytools/__init__.py` holds directory constants only.

## Import conventions

- Absolute imports everywhere, including within the same package (e.g., `from freeact.config.schema import ...` not `from .schema import ...`). No relative imports exist in the codebase.
- Standard library first, third-party second, local imports last.
- Circularity escapes: `agent/subagents.py` imports `Agent` inside `run_task()` (and under `TYPE_CHECKING`); `agent/executor.py` imports `SubagentRunner` under `TYPE_CHECKING` only.
