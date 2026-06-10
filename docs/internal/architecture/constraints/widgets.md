# Widget Constraints

## TrackedCollapsible (`freeact/terminal/view.py`)

All conversation boxes are `TrackedCollapsible`, which distinguishes user toggles from programmatic changes:

- Programmatic changes MUST go through `set_collapsed()` (sets a `_programmatic` flag); assigning `collapsed` directly would be recorded as a user toggle.
- User toggles are detected in the public `watch_collapsed()` observer (runs in addition to Textual's private `_watch_collapsed`) and posted as `UserToggled`. NEVER override `_on_collapsible_title_toggle` instead: Textual dispatches that handler for every class in the MRO, so it double-fires.
- `ConversationView` records `UserToggled` into `CollapsePolicy.manual_collapsed`.

## CollapsePolicy (`freeact/terminal/view.py`)

One object owns all collapse state. Resolution precedence in `apply()`:

```
expand_all_override > manual toggle > forced expansion > configured state
```

Manual beats forced so an active subagent task can be manually collapsed and stays collapsed as children mount. Forced expansion covers the pending-approval pin and active subagent tasks (`set_forced`); configured state comes from `TerminalSection` collapse settings (`set_configured`). Mount boxes via `ConversationView.mount_box(...)`, which registers them with the policy; never flip `collapsed` ad hoc.

## Box factories (`freeact/terminal/widgets.py`)

Two generic factories replace per-kind creators:

- `create_box(*children, title, agent_id, collapsed, classes) -> TrackedCollapsible`
- `create_action_box(*children, title, agent_id, classes) -> tuple[TrackedCollapsible, Vertical]` -- appends a `tool-trace-container` `Vertical` (inside a `tool-call-content` wrapper) that nested tool results mount into.

Titles are formatted by `_titled(label, agent_id)` as `[agent-id] <label>`. Tool-call content rendering per ToolCall type lives in the `_RENDERERS` registry in `freeact/terminal/approvals.py`, not in widgets.py.

Deliberately distinct widgets (do not fold into the generic factories):

- `PromptInput`, `ApprovalBar` (whose `display_text` attribute is named to avoid shadowing Textual's `Widget.display` reactive).
- `create_markdown_box()` for streaming thoughts/responses; `create_user_input_box()`; `create_error_box()`.
- `create_exec_output_box()` returning a streaming `RichLog`, finalized by `finalize_exec_output()`.
- `diff_content()` for FileEdit diffs.

## Text selection

Textual's selection only works with `Content`/`Text` visuals:

- Never pass Rich `Syntax` directly to `Static`; use `syntax_content(code, lexer)` (which strips token backgrounds via `_syntax_to_content` so the selection highlight shows) or `Static(text, markup=False)`.
- `RichLog` does not support selection; `finalize_exec_output()` replaces it with a `Static` after streaming completes.
