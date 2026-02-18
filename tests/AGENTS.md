# Testing Guidelines
- Unit tests (`tests/unit/`): `FunctionModel(stream_function=...)` for test models. Stream functions receive `(messages, info)` where `info.function_tools` contains available tools.
- Test helpers live in `tests/helpers/` (import from `tests.helpers`):
  - `tests/helpers/streams.py`: type aliases (`DeltaToolCalls`, `CodeExecFunction`, ...), `get_tool_return_parts`, `create_stream_function`, `create_task_stream_function`
  - `tests/helpers/agents.py`: `create_test_config`, `patched_agent`, `unpatched_agent`, `StreamResults`, `collect_stream`
- `patched_agent`: Agent with mocked code executor for unit tests.
- `unpatched_agent`: Agent with real ipybox kernel. Required for subagent tests.
- `collect_stream()`: Consumes `agent.stream()`, auto-approves via `approve_function`, collects events into `StreamResults`.
- `get_tool_return_parts(messages)`: Detects post-tool-execution model calls (messages ending with `ToolReturnPart`).
- Parent vs subagent in shared stream functions: `"subagent_task" in [t.name for t in info.function_tools]`. Parent has it, subagent does not.

## Config setup in tests
- Use `create_test_config()` from `tests.helpers` to create test configs. It handles `_ConfigPaths`, `agent.json`, and accepts `**overrides` for any config attribute.
- Never hardcode `.freeact` or other config directory names. Always derive paths via `_ConfigPaths(tmp_dir)` (e.g., `_ConfigPaths(tmp_dir).freeact_dir`).
- `agent.json` must include `"model"` (required field). Use `{"model": "test"}` as minimal config.
