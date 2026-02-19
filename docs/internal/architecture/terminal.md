# Terminal UI Architecture

First-orientation map for the Textual-based terminal UI (`freeact/terminal/default/*`).
Read this first, then follow code references for details.

## Entry Point

- `freeact/cli.py` uses `Terminal` unless `--legacy-ui` is set.
- `freeact/terminal/default/__init__.py` creates `FreeactApp` and passes:
  - `agent.stream`
  - `PermissionManager`
  - main `agent_id`

## Main Controller

- `freeact/terminal/default/app.py` (`FreeactApp`) is the terminal orchestrator.
- Two UI regions:
  - `#conversation` (rendered history)
  - `#prompt-input` (user input)
- One active turn at a time: `_process_turn()` runs under `@work(exclusive=True)`.

## Event Flow

- Prompt submit: `PromptInput.Submitted` -> `convert_at_references()` -> `parse_prompt()` -> `agent_stream(...)`.
- Stream events map to UI:
  - `Thoughts*` / `Response*`: markdown stream boxes
  - `ApprovalRequest`: approval UI + decision gate
  - `CodeExecutionOutput*`: execution output box
  - `ToolOutput`: normalized output box

## Boundaries

- `tool_adapter.py`: raw tool payloads -> canonical UI models (`tool_data.py`).
- `widgets.py`: all prompt/approval widgets and box factories.
- `screens.py`: modal file picker for `@` insertion.
- `permissions.py`: pre-approval and persisted/session allow-lists.

## Keyboard Semantics

- `PromptInput`: `Enter` submit, `Ctrl+J` newline, `Alt+Enter` -> `Ctrl+J`.
- Approval decisions can come from `ApprovalBar` or app-level hotkeys (`enter`, `y`, `n`, `a`, `s`).

## Testing

- Terminal test patterns live in `tests/AGENTS.md`.
