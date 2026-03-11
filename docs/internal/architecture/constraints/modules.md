# Module Boundary Constraints

## Package `__init__.py` files are re-exports only

No function or class definitions in `__init__.py`. They contain only imports from submodules and an `__all__` list. No module-level docstrings.

- `freeact/agent/__init__.py`: re-exports from `call`, `core`, `events`.
- `freeact/agent/config/__init__.py`: re-exports from `config`, `skills`, plus constants.
- `freeact/preproc/__init__.py`: re-exports from `prompt`.
- `freeact/terminal/__init__.py`: re-exports from `app`, `config`.
- `freeact/__init__.py`, `freeact/tools/__init__.py`: empty (no re-exports needed).
- `freeact/tools/pytools/__init__.py`: directory constants only.

## Import conventions

- Absolute imports everywhere, including within the same package (e.g., `from freeact.agent.config.prompts import ...` not `from .prompts import ...`).
- Standard library first, third-party second, local imports last.

No relative imports exist in the codebase.

## Dependency direction

```
cli.py
  -> Agent (agent/core.py)
  -> TerminalInterface (terminal/app.py)
  -> PermissionManager (permissions.py)
  -> Config (agent/config/, terminal/config.py)
  -> PersistentConfig (config.py)

terminal/app.py
  -> agent events and call types (agent/events.py, agent/call.py)
  -> PermissionManager (permissions.py)

agent/core.py
  -> agent/call.py, agent/events.py, agent/store.py
  -> agent/_supervisor.py, agent/_subagent.py
  -> tools/utils.py

agent/config/config.py
  -> PersistentConfig (config.py)

terminal/config.py
  -> PersistentConfig (config.py)

permissions.py
  -> agent/call.py (ToolCall base only)
```

The terminal depends on agent types but the agent does not depend on the terminal. The permission module depends on the `ToolCall` base class but not on agent core. Config classes inherit from `PersistentConfig` in the top-level `freeact/config.py`.
