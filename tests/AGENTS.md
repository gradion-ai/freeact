# Testing Guidelines
- Unit tests (`tests/unit/`): `FunctionModel(stream_function=...)` for test models. Stream functions receive `(messages, info)` where `info.function_tools` contains available tools.
- `patched_agent` (`tests/conftest.py`): Agent with mocked code executor for unit tests.
- `unpatched_agent` (local to integration test files): Agent with real ipybox kernel. Required for subagent tests.
- `collect_stream()`: Consumes `agent.stream()`, auto-approves via `approve_function`, collects events into `StreamResults`.
- `get_tool_return_parts(messages)`: Detects post-tool-execution model calls (messages ending with `ToolReturnPart`).
- Parent vs subagent in shared stream functions: `"subagent_task" in [t.name for t in info.function_tools]`. Parent has it, subagent does not.
