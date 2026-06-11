# Target Architecture

Design for the greenfield rewrite (branch `wip-rewrite`). Companion to
[behavior-inventory.md](behavior-inventory.md), which defines WHAT must work; this document
defines HOW it is structured. Status: IMPLEMENTED (phases 3-6 complete, 2026-06-10);
kept as the historical design record. The living rules reference is
docs/internal/invariants.md (distilled from the phase-6 architecture docs).

Agreed constraints (see memory/redesign decisions): single package with a `freeact[search]`
extra; unified TOML config with minimal defaults and one-line tool opt-ins; tests rewritten
against new interfaces; quality and simplicity outrank breaking changes.

## 1. Design principles

1. One component, one job. The pre-rewrite `Agent` (774 lines) and `TerminalApp` (1053
   lines) each mixed five or more concerns; no new component may own more than one.
2. The event stream is the only boundary between SDK and UI. The terminal renders
   `AgentEvent`s and resolves `ApprovalRequest`s; it never reaches into agent internals.
3. Parse, then resolve. Config loading is pure deserialization; everything that touches
   the environment (env vars, model instantiation, server table expansion) happens in an
   explicit resolution step.
4. One source of truth per piece of state. Message history lives in the session, not in a
   parallel in-memory list. Approval state lives in the approval gate. Collapse state lives
   in one place in the TUI.
5. Structured signals, not string matching. Rejection, interruption, and truncation are
   typed fields, not substrings.
6. Plain `match`/`case` for closed, local variant sets (the ToolCall types ARE such a
   set); a registry only where third parties genuinely extend (terminal renderers).

## 2. Package layout

```
freeact/
  __init__.py            # re-exports: Agent, AgentConfig, events, ApprovalRequest, ...
  cli.py                 # arg parsing, .env autoload, wiring, agent+TUI lifecycle ownership
  events.py              # AgentEvent types + Phase (SDK surface, no internal imports)
  toolcalls.py           # typed ToolCall hierarchy, from_raw classification, pattern
                         # suggest/parse incl. shell pattern generalization
  permissions.py         # typed rules, PermissionManager, default rule set
  config/
    schema.py            # pydantic models mirroring config.toml ([agent], [terminal])
    load.py              # locate/read config.toml; init() writes commented defaults,
                         # creates runtime dirs, materializes bundled skills
    resolve.py           # ResolvedRuntime + the preset table (search/fetch/discovery)
    prompts.py           # system prompt composition
    prompts/             # system.md + section templates
    skills.py            # skill discovery + bundled skill materialization
    templates/skills/    # bundled skills
  agent/
    agent.py             # Agent: public API + turn loop + CancelToken
    approvals.py         # ApprovalGate: single approval mechanism
    executor.py          # ToolExecutor: routes tool calls, owns the kernel bridge
    mcp.py               # MCPServerManager: lifecycle, tool defs, call dispatch, srt wrap
    subagents.py         # SubagentRunner: child agents, event bridging, concurrency
    session.py           # Session: history + persistence + overflow (single source of truth)
    shell.py             # PORT: shell command extraction + composite splitting
    tooldefs/            # built-in tool definitions (ipybox, subagent_task) + loader
  tools/                 # MCP servers (subprocess entry points, no agent imports)
    security.py          # PORT: untrusted-content wrapping
    fetch.py
    gsearch.py
    bsearch.py
    filesystem/          # PORT: processing.py as-is; server.py thin MCP wrapper
    pytools/
      apigen.py          # mcpygen wrapper (code-mode API generation)
      categories.py
      basic.py           # basic discovery MCP server
      hybrid/            # PORT: whole stack; packaged as freeact[search] extra
  terminal/
    app.py               # Textual App: lifecycle, bindings, prompt input + hints bar,
                         # focus; no AgentEvent-type knowledge
    dispatcher.py        # AgentEvent -> view routing (incl. subagent nesting by corr ids)
    view.py              # ConversationView: mounting, scrolling, CollapsePolicy
    approvals.py         # ApprovalController: bar lifecycle, decisions, permission writes
    widgets.py           # box factories + PromptInput, ApprovalBar, stream widgets
    screens.py           # file picker, skill picker
    clipboard.py         # PORT
```

Dependency direction (documented in the rewritten constraints docs):
`tools` -> nothing internal except `security`; `toolcalls` -> nothing internal;
`events` -> `toolcalls` (ApprovalRequest carries the typed call);
`permissions` -> `toolcalls`; `config` -> nothing internal; `agent` -> `events`,
`toolcalls`, `config`; `terminal` -> `events`, `toolcalls`, `permissions`, `config`;
`cli` -> everything. `agent` never imports `terminal` or `permissions`: the SDK stays
policy-free, the embedder decides approvals (section 6).

Placement notes resolving review findings:
- `Phase` lives in events.py (terminal needs `Cancelled.phase` without importing agent).
- Shell PATTERN suggestion (generalize a command to a glob) lives in toolcalls.py with
  the rest of the pattern symmetry methods; shell EXTRACTION/SPLITTING (parsing code for
  `!`/`%%bash`, composite splitting) lives in agent/shell.py. The terminal only ever
  needs patterns, never extraction.
- Built-in (non-MCP) tool definitions are data files under agent/tooldefs/, loaded by
  executor (ipybox tools) and subagents (subagent_task tool).
- `.env` autoload happens in cli.py.

## 3. Agent core

### 3.1 Components

**Agent** (agent.py). Public API per inventory section 1: constructor (config, agent_id,
session_id, sandbox, sandbox_config), async context manager, `start/stop`,
`stream(prompt, max_turns)`, `cancel()`, `session_id`, `tool_names`, `agent_id`, `model`,
`model_settings`. Owns the turn loop and `max_turns` enforcement:

```
async def stream(prompt, max_turns=None):
    session.append(user_message(prompt))
    while turns_remaining:
        async for ev in model_turn():        # stream LLM; yield Thoughts*/Response*
            yield ev
        if no tool_calls: return
        returns, media = [], []
        async for ev in executor.run(tool_calls):   # merged concurrent execution
            yield ev                          # ApprovalRequest / chunks / outputs
            collect returns, media
        session.append(model_response, tool_returns, media_parts)
        if any return is rejected: yield Response("Tool call rejected"); return
```

Media flow (review C5): binary MCP results and kernel-produced images reach the model as
media parts appended alongside the tool returns (pre-rewrite behavior, inventory 7); the
executor surfaces them, the turn loop appends them via Session.

Cancellation: `CancelToken` (in agent.py) + `Phase` (events.py: BETWEEN_TURNS,
LLM_STREAMING, TOOL_EXECUTION). Checks happen at named phase boundaries via one helper
that emits `Cancelled` and APPENDS synthetic "Interrupted by user" returns for orphaned
tool calls. Cancellation NEVER rolls history back (inventory 6 INVARIANT: history stays
valid for resume); rollback exists only on turn exceptions, as a separate path.

**ApprovalGate** (approvals.py). The only code that creates and resolves
`ApprovalRequest`s; used by every approval site: top-level tool calls (MCP, subagent
task, kernel reset), code actions, intercepted shell / shell magic sub-commands, and
PTCs. Responsibilities: race decision vs CancelToken and `approval_timeout` (timeout =
rejection); guarantee exactly-once resolution including the abandonment case (consumer
closes the stream while an approval is pending -> that approval is rejected exactly
once, inventory 5 INVARIANT); produce a typed `Decision` (approved | rejected |
cancelled | timed_out). The old code had this logic in three diverging copies.

**ToolExecutor** (executor.py). Routes each model tool call: code execution, kernel
reset, MCP (via MCPServerManager), subagent task (via SubagentRunner), unknown tool
(error return, NO approval). Owns the kernel bridge:
- constructs the ipybox executor with working_dir (cwd reset after each action is
  ipybox behavior wired here), images_dir, kernel env, sandbox settings,
  execution_timeout (enforced by ipybox so approval wait time is excluded, inventory 3
  INVARIANT; the gate never wraps execution in its own timeout);
- serializes kernel access (code actions and reset share one kernel; one lock here);
- streams `CodeExecutionOutputChunk`s as they arrive; on completion calls
  `session.materialize(...)` ONCE on the final output (chunks never materialize, which
  is what guarantees exactly one overflow file, inventory 8) and builds the final
  `CodeExecutionOutput` with text/images/`truncated` from the materializer result;
- intercepts shell commands (agent/shell.py extraction + composite splitting), requests
  per-sub-command approval through the gate, rejecting the whole command if any
  sub-command is rejected; sets `approval_rejected` on the final output event;
- emits all events with correct corr ids at construction time (no post-hoc mutation of
  frozen events).

**MCPServerManager** (mcp.py). Server lifecycle (concurrent start/stop on a TaskGroup),
tool definition loading, per-server tool exclusion, call dispatch with
exception-to-error-text conversion, binary content support, srt sandbox wrapping of
server commands when sandbox mode is on.

**SubagentRunner** (subagents.py). Builds the child runtime (inventory 9 inheritance
incl. sandbox settings; subagents off; discovery sync/watch off), spawns a child `Agent`
with `sub-` id, bridges its events into the parent stream (parent_corr_id set at
emission), enforces the `max_subagents` semaphore, propagates parent cancellation,
converts child failure to an error ToolOutput.

**Session** (session.py). Single source of truth for message history. API: `messages`,
`append(...)`, `rollback(n)` (exception path only), `materialize(result) ->
(content, truncated, file_path|None)`. Persistence is a constructor strategy:
`PersistentStore` (JSONL, incremental append, crash-tolerant tail, fidelity round-trip,
per-agent files, tool-results dir with sanitized extensions, inline fallback on write
failure) or `EphemeralStore` when persistence is disabled. Resume loads main history
only.

### 3.2 Event model (events.py)

Same event set as inventory section 2 (frozen dataclasses, chunk + final pairs,
agent_id/corr_id/parent_corr_id). Changes:
- `CodeExecutionOutput.approval_rejected: bool` field (set by the executor); the
  "ApprovalRejectedError:" string scan disappears from the SDK. The in-kernel error
  string shown to the model remains.
- `ApprovalRequest` keeps `approve(bool)` / `approved()` (public, inventory-pinned) but
  is constructed only by ApprovalGate.
- `Cancelled.phase: Phase` (str enum, same wire values).

### 3.3 Tool call typing (toolcalls.py)

The `ToolCall` hierarchy (CodeAction, ShellAction, FileRead/Write/Edit, GenericCall) with
its symmetry methods (from_raw classification, to/from pattern, to_display, permission
entry serialization) stays a closed set with a single `from_raw` match in this module
(design principle 6; the earlier idea of a decorator registry here is dropped per
review). Extension cost for a new call type: the class + match arm here, a rule class in
permissions.py, a renderer entry in the terminal registry. UI and permissions key off
the classes, so nothing else changes.

## 4. Configuration

### 4.1 File: `.freeact/config.toml`

Human-owned. Written once by `freeact init` (commented defaults) and never rewritten by
the app afterwards. Consequence (amends inventory 17): there is no programmatic
"save arbitrary config" API; config flows one way, file -> schema -> resolve.

```toml
[agent]
model = "google-gla:gemini-3.5-flash"
# execution_timeout = 300.0     # seconds; omit for default, set 0 to disable
# approval_timeout = 60.0       # seconds; omit = wait forever
# enable_persistence = true
# enable_subagents = true
# max_subagents = 5
# images_dir = "images"
# tool_result_inline_max_bytes = 32768
# tool_result_preview_chars = 2048

[agent.model_settings]
google_thinking_config = { thinking_level = "medium", include_thoughts = true }

# [agent.provider_settings]
# api_key = "${MY_KEY}"

[agent.tools]
# One-line opt-ins for bundled tool servers (minimal defaults: everything off except
# the built-ins code actions require: code execution + filesystem).
# search = true            # google search (code mode); needs GEMINI_API_KEY
# fetch = true             # web fetch (code mode)
# discovery = "basic"      # or "hybrid" (needs freeact[search]); omit for none

# [agent.kernel_env]
# MY_VAR = "${MY_VAR}"

# Custom MCP servers, full expressiveness (stdio or HTTP):
# [agent.mcp_servers.github]        # JSON tool calling
# command = "..." ; args = [...] ; env = { TOKEN = "${GITHUB_TOKEN}" }
# exclude_tools = ["..."]
# [agent.ptc_servers.github]        # code mode (generated Python APIs)
# ...

[terminal]
# collapse_thoughts_on_complete = true
# collapse_exec_output_on_complete = true
# collapse_approved_code_actions = false
# collapse_approved_tool_calls = true
# collapse_completed_subagent_tasks = true
# collapse_tool_outputs = true
# keep_rejected_actions_expanded = true
# pin_pending_approval_action_expanded = true
# expand_all_toggle_key = "ctrl+o"
```

Permissions do NOT live in config.toml: they are machine-written at approval time
("allow always"), and rewriting a human-edited TOML file from code clobbers comments.
They live in `.freeact/permissions.toml`, machine-managed (written with `tomli-w`;
optional rule fields are key-omitted since TOML has no null), seeded with the default
rule set by the embedder calling `PermissionManager.init()` (cli.py does this; config/
does not depend on permissions). No migration from the old permissions.json: old files
are ignored (breaking change; losing allow-rules is fail-safe, users get re-prompted).

### 4.2 Parse / resolve split

- `schema.py`: `FreeactConfig { agent, terminal }`. Frozen pydantic models, pure data,
  no env access, no I/O, no model instantiation. Validates types, ranges, preset names,
  `${VAR}` syntax.
- `load.py`: `load(working_dir) -> FreeactConfig` (missing file -> defaults);
  `init(working_dir)`: write commented defaults, create runtime dirs
  (sessions/generated/plans/skills), materialize bundled skills without overwriting
  user-modified ones.
- `resolve.py`: `resolve(config, env=os.environ) -> ResolvedRuntime`: model instance
  (pydantic-ai), full MCP/PTC server tables (preset table expanded into server configs,
  `${VAR}` substituted, missing vars raise here naming the variable), kernel env (HOME
  inheritance, PYTHONPATH with generated dir), workspace paths (sessions, generated,
  images, search db). `for_subagent()` derives the child runtime. Enabling a preset
  whose extra is missing (`discovery = "hybrid"` without `freeact[search]`) fails here
  with an install hint.

This removes `model_post_init` resolution and every `object.__setattr__` workaround.
TOML I/O: stdlib `tomllib` for reads, `tomli-w` (new small dependency) for the two
machine-written files (init-time config.toml, permissions.toml).

## 5. Terminal

**app.py**: Textual App subclass. Bindings, focus, screen stack, lifecycle, prompt input
handling (submission, empty-input warning, @ and / trigger detection, paste), the hints
bar (state-driven: idle/turn-in-progress/input-nonempty). Knows turn state but no
AgentEvent types. Receives `stream`/`cancel`/agent metadata as callables/values from
cli.py, which owns the `async with agent:` lifecycle around `app.run_async()`.

**dispatcher.py**: consumes the agent event stream for a turn. Routing per inventory 2
and 20: main-agent thoughts/responses -> view; execution chunks/outputs -> the box
owning their corr_id; subagent events -> the task box owning their parent_corr_id;
approval requests -> ApprovalController. Owns the turn-scoped UI state: corr_id ->
container map (populated via a registration callback when ApprovalController or the
view mounts a box) and the live stream handles (thoughts/response markdown streams,
exec-output logs keyed by (agent_id, corr_id)).

**view.py**: ConversationView (mounting, auto-scroll/anchor, banner with version and
cwd, error boxes) plus CollapsePolicy: one object owning all collapse state with the
PRE-REWRITE precedence, verified against inventory 20:

```
expand_all_override > manual > forced(pending-approval pin, active subagent task) > configured
```

(manual beats forced so an active subagent task can be manually collapsed and stays
collapsed as children mount; review C12). Programmatic vs user toggles are distinguished
by a Collapsible subclass intercepting the user toggle path, pinned by a pilot test
against the Textual version (review F3), replacing the suppression counter.

**approvals.py**: ApprovalController: builds the approval/tool-call box via a renderer
registry keyed by ToolCall class, registers it with the dispatcher's container map,
pre-approval check (PermissionManager / skip-permissions), approval bar lifecycle
(Y/n/a/s/Enter/Escape), pattern editing seeded from the call's suggested pattern,
allow-always/allow-session persistence, resolving the `ApprovalRequest`.

**widgets.py**: one generic collapsible-box factory and one syntax-highlighted
selectable-content factory replace the eight near-identical `create_*_box` functions;
the genuinely distinct widgets remain separate: PromptInput, ApprovalBar, markdown
stream wiring, diff rendering for FileEdit, and the streaming RichLog -> selectable
Static finalization (the selection/finalization behavior is inventory 20 contract and
wins over factory uniformity).

Pickers, clipboard, selection/copy/paste: ported per inventory 20.

## 6. Permissions

Typed rules as a pydantic discriminated union (one rule class per ToolCall type), each
owning its `matches(call, working_dir)`. Path-matching semantics ported verbatim
(security INVARIANTs, inventory 11), with the old integration test cases ported verbatim
as the seed of the new suite. Evaluation order and default rule set unchanged. Storage:
`.freeact/permissions.toml`; session tier in memory only. `PermissionManager` keeps its
small API (`init/load/save/is_allowed/allow_always/allow_session`; ask rules come from
defaults and the permissions file, there is no ask_* method, matching the old API).

The SDK stays policy-free: `Agent` emits `ApprovalRequest`s; the embedder decides.
PermissionManager is a library the terminal (or any embedder) uses.

## 7. Packaging

- Default install: SDK + CLI/TUI + filesystem/fetch/gsearch/bsearch tools + basic
  discovery. Dependencies: pydantic-ai, ipybox, mcpygen, textual, rich, pyyaml, pillow,
  python-dotenv, trafilatura, google-genai, tomli-w, aiostream (see open decision 2).
- `freeact[search]`: sqlite-vec + watchfiles, enables `discovery = "hybrid"`.
- Entry point: `freeact = freeact.cli:main`; `freeact run` kept as explicit alias of the
  default command (open decision 3).

## 8. Testing strategy

- Unit tests target components through their real interfaces (ApprovalGate, Session,
  ToolExecutor with a fake kernel bridge, CollapsePolicy, dispatcher with a scripted
  event stream). The old suite's mock scaffolding is not recreated.
- Integration tests preserve the old suite's behavior coverage: real kernel execution,
  MCP round-trips, permission semantics (cases ported verbatim), session resume,
  subagent flows, TUI flows via Textual pilot.
- Each test file states which inventory sections it covers; a phase is done when every
  inventory item for that phase maps to a test or is explicitly covered-by-port. New
  coverage for pre-rewrite gaps (inventory 21): gsearch contract, approval timeout,
  sandbox smoke test (may be marked manual).
- Acceptance harnesses come FIRST where risk is concentrated (section 10).

## 9. Build order (phases 3-6 of the plan)

1. Core SDK: events, toolcalls, config, session, approvals + merge helper (with ported
   abandonment/cancellation invariant tests green before anything builds on them),
   executor (fake bridge, then ipybox), mcp, subagents, agent. Inventory 1-12, 17.
2. Tools: port security/filesystem/hybrid, fetch/bsearch, gsearch with new tests, basic
   discovery, apigen wiring. Inventory 13-16.
3. Terminal: port the pilot test suite first as the acceptance harness, then
   widgets/view/dispatcher/approvals/app, pickers, clipboard. Inventory 18-20.
4. Packaging, extras, user docs rewrite (config format), architecture constraint files
   rewritten for this design.

Old code is deleted from the branch as each phase replaces it; `main` stays the reference.

## 10. Known risks and mitigations (from adversarial review)

1. Executor bridge + event merging + ApprovalGate carry the densest cluster of
   INVARIANTs (abandonment-rejects-once, cancel-during-approval, composite rejection,
   timeout-excludes-approval, synthetic returns). The abandonment INVARIANT currently
   rides on GeneratorExit propagating through `aiostream.merge` into the producer
   generators; a TaskGroup-based replacement turns consumer close into task
   cancellation, which does NOT reach `except GeneratorExit` handlers and needs
   shielding for the reject call. Mitigation: build ApprovalGate + merge helper first;
   keep aiostream until a replacement passes the ported invariant tests.
2. The terminal's interacting micro-behaviors (collapse precedence, subagent task
   transitions, root-level subagent approval bars, exec-log finalization). Mitigation:
   pilot tests ported before the implementation; CollapsePolicy specified from the old
   `apply()` semantics, not intuition.
3. Config/permissions funnel everything; omissions there are silent. Mitigation: a
   checklist test mapping every inventory 17/18 key to a schema field and resolve
   behavior; permission matching tests ported verbatim before the storage format
   changes.

## 11. Phase-3 implementation notes (deviations from the design above)

Recorded after building the core SDK; all are simplifications, none change behavior:

1. `ResourceSupervisor` was kept (agent/supervisor.py) instead of a TaskGroup-based
   replacement: proven, 50 lines, used by executor and MCP manager.
2. `aiostream` stays (open decision 2 resolved by test outcome): the ported invariant
   tests pin its close-propagation semantics; a key finding is that under merge
   backpressure producers sit suspended AT the yield, so abandonment protection lives
   at the approval yield sites (executor) plus a resolve-on-unwind guarantee in
   ApprovalGate.decide. NEW vs pre-rewrite: top-level approval abandonment now also
   resolves the request as rejected (the old code only unblocked in-kernel approvals).
3. `CancelToken` lives in agent/approvals.py (not agent.py) to keep the dependency
   graph acyclic; the preset table lives in config/resolve.py (no presets.py).
4. Session uses `store: SessionStore | None` instead of an EphemeralStore class; the
   None checks are encapsulated in Session.
5. MCPServerManager does NOT auto-wrap servers with srt in sandbox mode; matching old
   behavior, srt wrapping is user-level server config (docs/sandbox.md guidance).
6. tooldefs JSON caches live in agent/tooldefs/ with their loader; the ipybox cache
   regeneration script from the old tools/utils.py was dropped (regenerate manually
   against a live ipybox when ipybox tool schemas change).
7. cli.py is a minimal stub (`freeact init` works; `run` reports the TUI rewrite) so
   the entry point stays valid until phase 5.

## 12. Decisions (resolved with maintainer, 2026-06-10)

1. RESOLVED: permissions live in a separate machine-managed `.freeact/permissions.toml`
   (section 4.1); config.toml stays human-owned. No migration of old permissions.json
   (fail-safe direction; users re-approve).
2. OPEN (decide by test outcome): `aiostream` kept until a small merge helper passes the
   ported abandonment/cancellation invariant tests (risk 1); replaced only then.
3. RESOLVED: `freeact run` kept as explicit alias of the default command.
4. RESOLVED: programmatic `Config.save()` dropped; the app writes config.toml only at
   init, config flows one way (inventory 17 amended, section 22 entry added).
