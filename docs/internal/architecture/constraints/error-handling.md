# Error Handling and Logging Constraints

## Error handling

- No custom exception classes. Uses built-in `ValueError`, `RuntimeError`, and stdlib `ExceptionGroup`.
- Error messages are descriptive and include context values (e.g. the missing env var names in `config/resolve.py`).
- Failures inside a turn become error text in tool results, not raised exceptions: MCP calls return `"MCP tool call failed: ..."` (`agent/mcp.py`), code execution exceptions become the final `CodeExecutionOutput` text (`agent/executor.py`), kernel reset failures return `"Kernel reset failed: ..."`, subagent failures yield `ToolOutput("Subagent error: ...")` (`agent/subagents.py`), unknown tool names return an error `ToolReturnPart` without approval.
- Multiple resource stop failures are collected into `ExceptionGroup` (`Agent.stop`, `MCPServerManager.stop`); a single failure is re-raised as-is.
- `from e` chains exceptions (`SessionStore`, `ResourceSupervisor.start` wraps the resource error in `RuntimeError`).
- Turn exceptions trigger session rollback in `Agent.stream`, then propagate; the terminal renders them as an expanded Error box (`create_error_box` in `TerminalApp._process_turn`) and re-enables input.

## Logging

Logging is minimal and uses the shared `"freeact"` logger:

- `logger = logging.getLogger("freeact")` in `freeact/cli.py`, `agent/agent.py`, `agent/executor.py`, `agent/mcp.py`, `tools/pytools/apigen.py`.
- `cli.configure_logging()` configures level/handler from `--log-level` and disables propagation.
- Used for diagnostics only (rollback failures, MCP server starts, ipybox cleanup rejections), never for normal output.
