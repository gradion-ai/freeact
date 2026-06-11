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

## Pre-release e2e sweep

Scenario checklist for a full regression sweep (last run 2026-06-11, 8/8 PASS;
findings: discovery-off default, PATH-resolved `python` for internal servers).
Each scenario runs in its own scratch dir (`/tmp/freeact-e2e-<name>`) with its
own tmux session so they can run in parallel; copy the workspace `.env` in.

1. Quickstart web search (search preset, grounded answer via google PTC)
2. Agent skills (`/skill` invocation, skill-guided flow)
3. Python packages (pre-installed deps, plot artifact verified on disk, kernel
   state across turns)
4. Saving code actions as tools (gentools api/impl split; NEW session discovers
   via pytools and imports instead of rewriting)
5. Sandbox mode (`--sandbox --sandbox-config`): allowed write/read in workdir;
   blocked write outside; blocked network domain; protected config file
6. Approval lifecycle (NO --skip-permissions): y executes; n leaves no side
   effect + "Tool call rejected"; `a` seeds pattern + appends one rule to
   permissions.toml; rule pre-approves after restart; Escape rejects pending
7. Custom PTC server (GitHub MCP via `[agent.ptc_servers.*]`; sources
   generated; PTC call grounded -- cross-check against the public API)
8. Session resume (`--session-id` across restart: recall from history while a
   kernel-variable probe fails; invalid UUID rejected)
9. Subagent delegation + mid-run Escape (nested `[sub-*]` rendering; interrupt
   reaches the subagent kernel in ~1s; synthetic interrupted returns in BOTH
   jsonl files; next turn clean)
10. Hybrid discovery (`freeact[search]` venv; search.db built; semantic
    `pytools_search_tools`; fetch PTC grounded)

Gotchas learned:

- Evidence: the Textual alternate screen drops scrollback; verify discovery /
  tool-call sequences from `.freeact/sessions/<id>/*.jsonl`, not the pane.
- A stale `VIRTUAL_ENV` from the shell profile misroutes bare `uv pip install`;
  pass `--python .venv/bin/python` or activate the venv.
- example.org returns 403 to Python's default User-Agent; use a browser UA for
  allowed-domain checks.
- Scenario 7 needs `GITHUB_API_KEY` in `.env`; sandbox startup is slower
  (allow 30s); first PTC launch generates sources (allow 90s).

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
