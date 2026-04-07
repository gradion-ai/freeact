# Terminal UI Architecture

First-orientation map for the Textual-based terminal UI (`freeact/terminal/*`).
Read this first, then follow code references for details.

## Entry Point

- `freeact/cli.py` creates `TerminalInterface` for interactive mode.
- `freeact/terminal/app.py` (`TerminalInterface`) creates `TerminalApp` and passes:
  - `agent.stream`
  - `PermissionManager`
  - main `agent_id`

## Main Controller

- `freeact/terminal/app.py` (`TerminalApp`) is the terminal orchestrator.
- Two UI regions:
  - `#conversation` (rendered history)
  - `#prompt-input` (user input)
- One active turn at a time: `_process_turn()` runs under `@work(exclusive=True)`.

## Event Flow

- Prompt submit: `PromptInput.Submitted` -> `convert_slash_commands()` -> `agent_stream(...)`.
- Stream events map to UI:
  - Main-agent `Thoughts*` / `Response*`: markdown stream boxes
  - `ApprovalRequest`: approval UI + decision gate
  - `CodeExecutionOutput*`: execution output box
  - `ToolOutput`: normalized output box
- Subagent `Thoughts*` / `Response*` are not rendered.
- All tool results nest inside their tool call widget via `corr_id` lookup against `_tool_call_boxes`.
- Subagent child events use `parent_corr_id` to route into the `subagent_task` container.
- Routing priority: `corr_id` -> `parent_corr_id` -> conversation root.

## Boundaries

- `clipboard.py`: platform clipboard adapter (`pbcopy/pbpaste`, `wl-*`, `xclip`/`xsel`, PowerShell) with local fallback.
- `config.py`: terminal UI collapse behavior and keybinding configuration.
- `widgets.py`: all prompt/approval widgets and box factories. `ApprovalBar` takes a `pattern` (seeds the inline edit input on `a`/`s`) and an optional `display_text` (the verbatim text shown in the bar; falls back to `pattern` when empty). The attribute is named `display_text` to avoid shadowing Textual's `Widget.display` reactive.
- `screens.py`: modal file picker for `@` insertion.
- `freeact/agent/call.py`: `ToolCall` type hierarchy, `suggest_pattern`, `suggest_display`, `parse_pattern`, `extract_tool_output_text`.
- `freeact.permissions.PermissionManager`: pre-approval and persisted/session allow-lists.

## Keyboard Semantics

- `PromptInput`: `Enter` submit, `Ctrl+J` newline, `Alt+Enter` -> `Ctrl+J`, `Escape` clears input when idle.
- Quit: `Ctrl+Q`.
- Expand/collapse override: `toggle_expand_all` (default `Ctrl+O`, configurable via `expand_all_toggle_key` in `terminal.json`).
- Copy selected text: `Cmd+C` / `Super+C`, `Ctrl+Shift+C`, `Ctrl+Insert`, `Ctrl+C`.
- Paste in prompt input: `Ctrl+V`, `Cmd+V` / `Super+V`, `Ctrl+Shift+V`, `Shift+Insert`.
- File picker: typing `@` at the prompt opens `FilePickerScreen`; `Enter` selects, `Escape` cancels.
- Clipboard model: OS clipboard is source of truth; Textual local clipboard is fallback cache.
- Approval decisions can come from `ApprovalBar` or app-level hotkeys (`enter`, `y`, `n`, `a`, `s`).

## Text Selection

Textual's selection requires widgets to render via `Content` (or `Text`). Two cases need handling:

- Rich `Syntax` produces a `RichVisual`, which bypasses selection. `_syntax_to_content()` converts `Syntax` to `Content`, stripping `bgcolor` from token spans so the `screen--selection` highlight can show through.
- `RichLog` streams chunks during execution but does not support selection. `finalize_exec_output` replaces the `RichLog` with a plain `Static` after streaming completes.

## Testing

- Terminal test patterns live in `tests/AGENTS.md`.
