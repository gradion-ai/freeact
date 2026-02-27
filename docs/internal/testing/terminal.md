# Terminal TUI Testing

## Pattern

- Use `TerminalApp` with `async with app.run_test() as pilot`.
- Use deterministic local `agent_stream` scenarios (no stateful/time-delayed demo mocks).
- After submit, sync with `await app.workers.wait_for_complete()`. Use short `pilot.pause(...)` only for transient UI mount timing.
- Assert stable selectors and state (`.response-box`, `.thoughts-box`, `.tool-output-box`, `collapsed`), not rendering internals.

## Test split

- `tests/unit/terminal/test_app.py`: app flow and approvals.
- `tests/unit/terminal/test_widgets.py`: widget metadata/state.
- `tests/unit/terminal/test_tool_adapter.py`: payload normalization.
