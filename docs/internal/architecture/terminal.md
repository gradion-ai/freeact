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

- Prompt submit: `PromptInput.Submitted` -> `convert_at_references()` -> `preprocess_prompt()` -> `agent_stream(...)`.
- Stream events map to UI:
  - `Thoughts*` / `Response*`: markdown stream boxes
  - `ApprovalRequest`: approval UI + decision gate
  - `CodeExecutionOutput*`: execution output box
  - `ToolOutput`: normalized output box

## Boundaries

- `clipboard.py`: platform clipboard adapter (`pbcopy/pbpaste`, `wl-*`, `xclip`/`xsel`, PowerShell) with local fallback.
- `config.py`: terminal UI collapse behavior and keybinding configuration.
- `tool_adapter.py`: raw tool payloads -> canonical UI models (`tool_data.py`).
- `widgets.py`: all prompt/approval widgets and box factories.
- `screens.py`: modal file picker for `@` insertion.
- `freeact.permissions.PermissionManager`: pre-approval and persisted/session allow-lists.

## Keyboard Semantics

- `PromptInput`: `Enter` submit, `Ctrl+J` newline, `Alt+Enter` -> `Ctrl+J`.
- Quit: `Ctrl+Q`.
- Expand/collapse override: `toggle_expand_all` (default `Ctrl+O`, configurable via `expand_all_toggle_key` in `terminal.json`).
- Copy selected text: `Cmd+C` / `Super+C`, `Ctrl+Shift+C`, `Ctrl+Insert`, `Ctrl+C`.
- Paste in prompt input: `Ctrl+V`, `Cmd+V` / `Super+V`, `Ctrl+Shift+V`, `Shift+Insert`.
- File picker: typing `@` at the prompt opens `FilePickerScreen`; `Enter` selects, `Escape` cancels.
- Clipboard model: OS clipboard is source of truth; Textual local clipboard is fallback cache.
- Approval decisions can come from `ApprovalBar` or app-level hotkeys (`enter`, `y`, `n`, `a`, `s`).

## Testing

- Terminal test patterns live in `tests/AGENTS.md`.
