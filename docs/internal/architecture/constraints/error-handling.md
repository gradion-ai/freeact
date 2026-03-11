# Error Handling and Logging Constraints

## Error handling

- No custom exception classes. Uses built-in `ValueError`, `RuntimeError`.
- Error messages are descriptive and include context values.
- Tool execution failures return error strings as `ToolResult` (not raised as exceptions).
- Multiple resource stop failures are collected into `ExceptionGroup`.
- `from e` clause used to chain exceptions.

## Logging

Logging is minimal. Only a few modules use it:

- `freeact/agent/core.py`, `freeact/agent/store.py`, `freeact/terminal/app.py`, `freeact/cli.py`, `freeact/tools/pytools/apigen.py`.
- Pattern: `import logging` at module level, `logger = logging.getLogger(__name__)` (or `"freeact"`).
- Used for diagnostics only, not for normal output.
