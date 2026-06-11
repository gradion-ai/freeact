# Invariants and Non-Obvious Rules

Everything here is a rule the code cannot explain by itself: violating it usually
compiles, passes a shallow review, and breaks something subtle. Component maps, API
surfaces, and flow narratives are deliberately NOT documented; read the source, it is
small and single-purpose per module. Tests pin most of these rules; this file explains
why, so neither the rule nor its test gets "simplified" away.

## Dependency direction

```
cli -> everything            terminal -> events, toolcalls, permissions, config
agent -> events, toolcalls, config        permissions -> toolcalls
events -> toolcalls          config, toolcalls, tools -> nothing internal
                             (tools/fetch+bsearch -> tools/security)
```

- `agent/` NEVER imports `terminal` or `permissions`: the SDK is policy-free; it emits
  `ApprovalRequest`s and the embedder decides.
- `terminal/` never imports `pydantic_ai`; `Phase` lives in `events.py` so the terminal
  reads `Cancelled.phase` without importing `agent/`.
- Shell PATTERN suggestion lives in `toolcalls.py` (terminal needs it); shell SPLITTING
  lives in `agent/shell.py` (only the executor needs it).
- `__init__.py` files are re-exports only; absolute imports everywhere; `.env` autoload
  and logging setup happen in `cli.py` only.

## Type conventions (exceptions to the obvious patterns)

- `AgentEvent` base is `kw_only=True` so subtypes can add positional fields after the
  base's defaulted id fields.
- `ApprovalRequest` is frozen yet carries a `Future`; `approve()` mutates the Future's
  internal state, never reassigns the field. Idempotent by design (`done()` check):
  cancellation/timeout and a late UI decision race on the same request.
- `PermissionsConfig` is deliberately NOT frozen (its lists are mutated in place);
  `CollapsePolicy` and the dispatcher's stream-state holders are deliberately mutable.
- No `model_post_init` resolution and no `object.__setattr__` anywhere; anything
  environment-dependent belongs in `config/resolve.py`.

## Configuration (`freeact/config/`)

- One-way flow: file -> schema -> resolve. `schema.py` stays pure data (no I/O, no env,
  no model instantiation). There is no programmatic "save config" API.
- `config.toml` is human-owned: written exactly once by `init()` as the literal
  commented template `DEFAULT_CONFIG_TOML` (a TOML writer cannot emit comments) and
  never rewritten by the app. Permissions live in the machine-managed
  `permissions.toml` instead (written with `tomli_w`).
- `${VAR}` substitution happens at resolve and missing vars raise naming the variable,
  EXCEPT `ptc_servers`: validated at resolve, returned unsubstituted (substitution
  happens at use by mcpygen / server start).
- `0` sentinels: `execution_timeout = 0` disables, `approval_timeout = 0` waits forever
  (`ResolvedRuntime` maps to `None`); TOML cannot encode null.
- All `.freeact/` layout knowledge lives in `Workspace`; never hardcode those paths.
- `config/` must not depend on `permissions.py`; `cli.py` wires both (permission
  seeding is the embedder's job).

## Permissions (security-critical; preserve exactly)

- Evaluation order: session-ask, always-ask, session-allow, always-allow. First match
  wins; ask beats allow; no match means not allowed.
- A relative path pattern (including bare `**`) NEVER matches an absolute path
  (`_path_matches` absoluteness check). Absolute paths under `working_dir` are
  normalized to relative first. This is what keeps the default `**` read-allow from
  exposing `/etc/passwd` or `~/.ssh/...`. `**/.env` is an ask rule and beats `**`.
- Path matching is `PurePosixPath.full_match` (`*` does not cross `/`); non-path
  fields use `fnmatch`. fnmatch nuance: `git status *` does NOT match bare
  `git status`, so commands need both entries; `git tag`/`git branch`/`git reflog`
  get ONLY the bare form because the `*` form would match destructive flags.
- Deliberately excluded from default allows: `find` and `env` (both can execute
  arbitrary commands) and everything via `shell_magic` (no defaults at all).
- Adding a ToolCall subtype touches exactly three places: `toolcalls.py` (class +
  `from_raw` arm), `permissions.py` (rule class + union + `rule_from_call` arm),
  `terminal/approvals.py` (`_RENDERERS` entry).

## Approval gate and async (`agent/approvals.py`, `agent/executor.py`)

- `ApprovalGate` is the only code that creates/resolves `ApprovalRequest`s.
- In `decide()`'s `finally`, resolve the request BEFORE reaping the approval waiter
  task: cancelling a task that awaits the request's future cancels the future itself,
  making later `approved()` calls raise instead of returning the decision.
- Under `aiostream.merge` backpressure, producer generators sit suspended AT the
  yield, so consumer close raises `GeneratorExit` exactly there: every
  `yield approval` site in the executor is wrapped in `except GeneratorExit:` that
  resolves the request as rejected (and rejects the ipybox-side request for in-kernel
  approvals) before re-raising. Do not replace `aiostream.merge` without re-running
  the abandonment/cancellation invariant tests; its close-propagation is pinned.
- `async for` does not close its iterator on early exit; the close chain is explicit:
  `Agent.stream` finally -> turn stream aclose -> `ToolExecutor.run` aclose -> merge
  exit -> per-call generators. Removing any link silently breaks abandonment.
- The kernel is a serialized resource (`_kernel_lock`: code actions and reset share
  it). `execution_timeout` is enforced BY ipybox so approval wait time is excluded;
  never wrap execution in an outer timeout.
- Sync file I/O from async code is wrapped (`arun` / `asyncio.to_thread`); known
  accepted exception: startup wiring in `cli.run` before the UI loop.

## Cancellation

- Flag-based (`CancelToken`, kept in `approvals.py` to stay acyclic); no
  `CancelledError` propagation for turn cancellation. `Agent.cancel()` also
  interrupts the kernel. Only the main agent clears the token (subagents share the
  parent's and must not clear it).
- INVARIANT (conversation coherence): after cancellation every tool call the model
  issued has a tool return in history (synthetic `"Interrupted by user"` returns),
  preserving `[tool_use] -> [tool_result]` sequencing so persisted history stays
  resumable. Cancellation NEVER rolls history back; `Session.rollback` is exclusively
  the turn-exception path.
- `Decision.CANCELLED` yields an interrupted return, NOT a rejected one, so
  cancellation does not trigger the rejection-ends-turn response. Approval timeout
  DOES count as rejection.
- INVARIANT: any tool return with `metadata["rejected"]` ends the turn with a final
  `"Tool call rejected"` response; nothing after the rejected action executes.

## Persistence (`agent/session.py`)

- `Session` is the single source of truth for history; nothing else writes it.
  JSONL envelopes forbid `meta.agent_id`; a malformed FINAL line is tolerated on load
  (crash mid-append), earlier malformed lines raise. Resume rehydrates main history
  only; `sub-*.jsonl` files are an audit record.
- Overflow materialization happens exactly once per result, on the FINAL output only
  (chunks never materialize): that is what guarantees one overflow file per result.
- If saving an overflow file fails, the content stays inline (no data loss).
  Extensions are sanitized to lowercase alphanumerics (no path traversal via
  media-type-derived extensions).

## Terminal (`freeact/terminal/`)

- NEVER override `_on_collapsible_title_toggle`: Textual dispatches that handler for
  every class in the MRO, so the base and override both run and the toggle
  double-fires. User-toggle detection lives in the public `watch_collapsed()`
  observer of `TrackedCollapsible`; programmatic changes MUST go through
  `set_collapsed()` (direct `collapsed =` assignment would be recorded as a user
  toggle).
- `CollapsePolicy.apply()` precedence: expand_all_override > manual > forced
  (pending-approval pin, active subagent task) > configured. Manual beats forced so
  an active subagent task can be manually collapsed and stays collapsed as children
  mount. Mount boxes via `ConversationView.mount_box` (registers with the policy);
  never flip `collapsed` ad hoc.
- Approval bars always mount at conversation root so subagent approvals stay visible
  inside collapsed task boxes. Event routing priority: `corr_id` ->
  `parent_corr_id` -> root.
- Text selection works only with `Content`/`Text` visuals: route Rich `Syntax`
  through `syntax_content()` (strips token backgrounds so the selection highlight
  shows); `RichLog` does not support selection, so `finalize_exec_output()` swaps it
  for a `Static` after streaming.
- Turn-scoped rendering state lives in the per-turn `EventDispatcher`; collapse state
  in `ConversationView.policy`; pending-approval state in the long-lived
  `ApprovalController`; `TerminalApp` owns only `_turn_in_progress`.

## Errors

- Failures inside a turn become error text in tool results, never raised exceptions
  (MCP calls, code execution, kernel reset, subagent failure, unknown tool). Turn
  exceptions roll history back and render as an Error box.
- No custom exception classes; multiple stop failures collect into `ExceptionGroup`.
- One shared `"freeact"` logger, diagnostics only; `cli.configure_logging` owns setup.

## Misc

- Built-in tool definitions (`agent/tooldefs/*.json`) are caches; regenerate manually
  against a live ipybox when its tool schemas change.
- `corr_id` contract: every event of a tool call carries the call's `corr_id` from
  construction (events are frozen; no post-hoc mutation). Subagent events keep their
  own `corr_id` and get `parent_corr_id` set at the bridge.
