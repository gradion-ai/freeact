# Agent Testing

## Test models

- Unit tests use `FunctionModel(stream_function=...)` for test models.
- Stream functions receive `(messages, info)` where `info.function_tools` contains available tools.

## Test helpers

Test helpers live in `tests/helpers/` (import from `tests.helpers`):

- `tests/helpers/streams.py`: type aliases (`DeltaToolCalls`, ...), `get_tool_return_parts`, `create_stream_function`, `create_task_stream_function`, `StreamResults`, `collect_stream`
- `tests/helpers/runtimes.py`: `create_test_runtime`, `patched_agent`, `unpatched_agent`, `FakeCodeExecutor`, `ApprovalRecorder`, `ipybox_shell_approval`, `ipybox_shell_magic_approval`, `ipybox_ptc_approval`

Key helpers:

- `create_test_runtime(tmp_dir, stream_function, mcp_servers=..., **agent_section_overrides)`: builds a `ResolvedRuntime` directly (bypassing config resolution) so tests control every value. Old-style `execution_timeout=None`/`approval_timeout=None` map to the schema's `0`.
- `patched_agent`: Agent whose kernel is a `FakeCodeExecutor`. Pass a `FakeCodeExecutor(script)` where `script(code)` is an async generator yielding real ipybox items (`ipybox.CodeExecutionChunk`, `ipybox.CodeExecutionResult`, `ipybox.ApprovalRequest` built via the `ipybox_*_approval` helpers with an `ApprovalRecorder`).
- `unpatched_agent`: Agent with real ipybox kernel. Required for subagent tests.
- `collect_stream()`: Consumes `agent.stream()`, auto-approves via `approve_function`, collects events into `StreamResults`.
- `get_tool_return_parts(messages)`: Detects post-tool-execution model calls (messages ending with `ToolReturnPart`). Note: only matches when the LAST message is the tool-return request; to collect all returns from a finished turn, scan `agent._session.messages` for `ModelRequest` parts.
- Parent vs subagent in shared stream functions: `"subagent_task" in [t.name for t in info.function_tools]`. Parent has it, subagent does not.

## Config setup

- Unit tests should use `create_test_runtime(tmp_dir)`; only config tests go through `freeact.config.load/init/resolve`.
- Workspace layout is derived from `working_dir / ".freeact"` via `freeact.config.Workspace`.
- `freeact.config.init(working_dir)` creates on-disk artifacts (config.toml, runtime dirs, bundled skills) when a test needs them.
