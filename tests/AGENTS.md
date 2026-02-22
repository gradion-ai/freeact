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
- Use `create_test_config()` from `tests.helpers` to create test configs with defaults and `**overrides` for any config attribute.
- `Config.freeact_dir` is derived from `working_dir / ".freeact"`.
- Persist config files explicitly with `await config.save()` when a test needs on-disk config artifacts.

## Terminal TUI testing pattern (`freeact/terminal`)
- Use `FreeactApp` with `async with app.run_test() as pilot`.
- Use deterministic local `agent_stream` scenarios (no stateful/time-delayed demo mocks).
- After submit, sync with `await app.workers.wait_for_complete()`. Use short `pilot.pause(...)` only for transient UI mount timing.
- Assert stable selectors and state (`.response-box`, `.thoughts-box`, `.tool-output-box`, `collapsed`), not rendering internals.
- Test split:
  - `tests/unit/terminal/test_app.py`: app flow and approvals.
  - `tests/unit/terminal/test_widgets.py`: widget metadata/state.
  - `tests/unit/terminal/test_tool_adapter.py`: payload normalization.
