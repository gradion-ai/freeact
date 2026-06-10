# Terminal UI Architecture

First-orientation map for the Textual-based terminal UI (`freeact/terminal/*`).
Read this first, then follow code references for details.

## Module map

- `app.py` (`TerminalApp`): Textual App. Bindings, focus, prompt input handling (submission, slash-command conversion, `@`/`/` picker triggers), the state-driven hints bar, clipboard integration, turn lifecycle (`_process_turn` under `@work(exclusive=True)`). Knows turn state but no `AgentEvent` types beyond passing the stream to the dispatcher. Receives `stream`/`cancel`/agent metadata as callables/values from `cli.py`, which owns the `async with agent:` lifecycle around `app.run_async()`.
- `dispatcher.py` (`EventDispatcher`): consumes one turn's agent events and routes them into the view. Owns the turn-scoped UI state: the `corr_id -> ToolCallBoxState` container map and the live stream handles (thoughts/response markdown streams, exec-output logs keyed by `(agent_id, corr_id, parent_corr_id)`). One dispatcher per turn; `finish()` releases forced expansion and clears the map.
- `view.py` (`ConversationView`, `TrackedCollapsible`, `CollapsePolicy`): mounting, auto-scroll, banner (version with build metadata stripped, `~`-relative cwd), and all collapse state. See [constraints/widgets.md](constraints/widgets.md).
- `approvals.py` (`ApprovalController` + `_RENDERERS`): builds the tool-call box via a renderer registry keyed by ToolCall class, registers it with the dispatcher's container map, pre-approval check (`PermissionManager.is_allowed` or `--skip-permissions`), approval bar lifecycle, pattern editing, allow-always/allow-session persistence, resolving the `ApprovalRequest`.
- `widgets.py`: generic box factories, `PromptInput`, `ApprovalBar`, selection helpers (`syntax_content`, `diff_content`, `finalize_exec_output`).
- `screens.py`: modal `FilePickerScreen` (`@` trigger; tree rooted at `/`, cursor at cwd, prefix-search navigation) and `SkillPickerScreen` (`/` trigger at prompt start).
- `clipboard.py`: platform clipboard adapter (macOS `pbcopy/pbpaste`; Linux `wl-*`/`xclip`/`xsel`; Windows PowerShell). OS clipboard is the source of truth; Textual's local clipboard is the fallback cache.

## Event routing (`EventDispatcher.dispatch`)

- Main-agent `ThoughtsChunk`/`ResponseChunk` stream into markdown boxes (created lazily, finalized on `Thoughts`/`Response`); subagent thoughts/responses are not rendered.
- `ApprovalRequest` -> `ApprovalController.handle(request, dispatcher)`.
- `CodeExecutionOutputChunk`/`CodeExecutionOutput` stream into a `RichLog` nested in the owning tool-call box; the final output finalizes the log into a selectable `Static`.
- `ToolOutput` renders a collapsed-by-default output box in the owning container; a root-level `ToolOutput` for a subagent task marks the task completed (collapse per config).
- `Cancelled` is a no-op in the dispatcher.
- Routing priority for the owning container: `corr_id` -> `parent_corr_id` -> conversation root. Subagent child events route into the `subagent_task` box via `parent_corr_id`.

## Approval flow

1. Dispatcher hands the `ApprovalRequest` to `ApprovalController.handle`.
2. The tool-call box is built from `_RENDERERS` and registered with the dispatcher (so later events with the same corr_id nest inside it), mounted with forced expansion when `pin_pending_approval_action_expanded` is set.
3. Pre-approved calls (permission match or skip-permissions) resolve immediately and follow the approved-collapse config; subagent task boxes get pinned active.
4. Otherwise an `ApprovalBar` mounts at conversation root (so subagent approvals stay visible inside collapsed task boxes), showing the call's display text (verbatim bash command, summarized shell script) or suggested pattern.
5. Decisions arrive via `ApprovalBar.Decided` or app-level hotkeys (`enter`/`y`/`n`; `a`/`s` open the editable pattern input, then persist `allow_always`/`allow_session` via `parse_pattern`); `check_action` gates hotkeys on pending/bar state. The controller resolves `request.approve(...)` and applies collapse config (rejected boxes stay expanded per `keep_rejected_actions_expanded`).
6. Escape during a turn calls `cancel()` and `reject_pending()` (see [cancellation.md](cancellation.md)).

## Keyboard semantics

- `PromptInput`: `Enter` submits (trimmed; empty input shows a warning), `Ctrl+J` newline, `Alt+Enter` mapped to `Ctrl+J` via an ANSI sequence registration, `Escape` clears non-empty input when idle.
- App: `Ctrl+Q` quits; `Escape` cancels the active turn; expand-all toggle key from config (default `ctrl+o`).
- Copy: `Ctrl+C` / `Super+C` / `Ctrl+Shift+C` / `Ctrl+Insert` -> `screen.copy_text` -> OS clipboard. Paste in `PromptInput`: `Ctrl+V` (TextArea built-in) / `Super+V` / `Ctrl+Shift+V` / `Shift+Insert`, reading the OS clipboard first.
- `@` at a word start opens the file picker (selection inserts the path, relative when under the working dir, else absolute); `/` at prompt start opens the skill picker; on submit `convert_slash_commands` turns `/skill args` into a `<skill>` tag.

## Turn-scoped state ownership

`TerminalApp` owns only `_turn_in_progress`. Per-turn rendering state lives in the `EventDispatcher` created per `_process_turn`. Pending-approval state (`_approval_future`, `_bar`) lives in the long-lived `ApprovalController`. Collapse state lives in `ConversationView.policy`. Stream exceptions render an expanded Error box and re-enable input.

## Testing

Terminal test patterns: `docs/internal/testing/terminal.md` and `tests/AGENTS.md`.
