# Testing Reference

Conventions: `@pytest.mark.asyncio` (not anyio); helpers import from `tests.helpers`.

## Agent tests

- Unit tests use `FunctionModel(stream_function=...)`; stream functions receive
  `(messages, info)` where `info.function_tools` lists available tools. Distinguish
  parent vs subagent in shared stream functions via
  `"subagent_task" in [t.name for t in info.function_tools]`.
- `create_test_runtime(tmp_dir, stream_function, mcp_servers=..., **agent_section_overrides)`
  builds a `ResolvedRuntime` directly, bypassing config resolution; old-style
  `execution_timeout=None`/`approval_timeout=None` map to the schema's `0`.
- `patched_agent`: Agent whose kernel is a `FakeCodeExecutor`. Drive in-kernel flows
  with `FakeCodeExecutor(script)` where `script(code)` is an async generator yielding
  real ipybox items (`CodeExecutionChunk`, `CodeExecutionResult`, and
  `ipybox.ApprovalRequest` built via `ipybox_shell_approval` /
  `ipybox_shell_magic_approval` / `ipybox_ptc_approval` with an `ApprovalRecorder`).
- `unpatched_agent`: real ipybox kernel; required for subagent tests.
- `collect_stream()` consumes `agent.stream()`, auto-approving via `approve_function`,
  into `StreamResults`.
- `get_tool_return_parts(messages)` matches only when the LAST message is the
  tool-return request; to collect all returns of a finished turn, scan
  `agent._session.messages` for `ModelRequest` parts.
- Only config tests go through `freeact.config.load/init/resolve`;
  `config.init(working_dir)` creates on-disk artifacts when a test needs them.

## Terminal tests

- `TerminalApp` with `async with app.run_test() as pilot`; deterministic local
  `agent_stream` scenarios (no stateful/time-delayed mocks).
- After submit, sync with `await app.workers.wait_for_complete()`; short
  `pilot.pause(...)` only for transient mount timing.
- Assert stable selectors/state (`.response-box`, `.thoughts-box`,
  `.tool-output-box`, `collapsed`), not rendering internals.
- Split: `test_app.py` app flow and approvals; `test_widgets.py` widget metadata.

## End-to-end (tmux)

Driven via the `freeact-interaction` skill.

- `.freeact/` is not in git; create with `uv run freeact init` when missing, then
  edit `.freeact/config.toml` for the scenario (e.g. an `[agent.ptc_servers.<name>]`
  table). API keys live in the repo's `.env`, loaded automatically on startup;
  `${VAR}` references resolve from it.
- Verify: task completes, no errors in scrollback
  (`tmux capture-pane -t agent -p -S -100`).
- PTC servers: prompt explicitly names the tool, approve the code action and the PTC
  call, verify the response is grounded in real external data.
