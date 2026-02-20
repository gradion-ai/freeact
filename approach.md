# Clipboard Unification Approach (Implemented)

## Goal

Make clipboard behavior deterministic across terminals by using the OS clipboard as the source of truth, with Textual local clipboard as fallback.

## Implementation Overview

### 1. Add clipboard adapter module

File: `freeact/terminal/default/clipboard.py`

Interface:

- `copy(text: str) -> bool`
- `paste() -> str | None`

Behavior:

- macOS: `pbcopy` / `pbpaste`
- Linux:
  - Wayland-first when `WAYLAND_DISPLAY` or `XDG_SESSION_TYPE=wayland`: `wl-copy` / `wl-paste --no-newline`
  - fallback: `xclip`, then `xsel`
  - x11/non-wayland starts with `xclip`, then `xsel`, then `wl-*`
- Windows:
  - `powershell -NoProfile -NonInteractive -Command "$input | Set-Clipboard"`
  - `powershell -NoProfile -NonInteractive -Command "Get-Clipboard -Raw"`
  - fallback to `pwsh` equivalents

Execution policy:

- subprocess timeout: `0.75s`
- non-zero exit, timeout, missing command, and OSError are treated as backend failure
- `paste()` returns empty string when clipboard is empty (not treated as failure)

### 2. Route app copy through adapter

File: `freeact/terminal/default/app.py`

- `FreeactApp.__init__` accepts optional `clipboard_adapter` for dependency injection in tests.
- Override `copy_to_clipboard`:
  - calls adapter `copy(text)` first
  - always mirrors text to `self._clipboard` (Textual local fallback cache)

### 3. Route prompt paste through adapter

Files:

- `freeact/terminal/default/app.py`
- `freeact/terminal/default/widgets.py`

Changes:

- `FreeactApp` exposes `read_clipboard_for_paste()`:
  - reads OS clipboard first (`adapter.paste()`)
  - if unavailable (`None`), falls back to `self.clipboard`
  - mirrors successful OS paste into local clipboard cache
- `PromptInput` receives optional `clipboard_reader`.
- `PromptInput.action_paste()` is overridden to use that reader.

### 4. Keybinding policy

Copy (`FreeactApp.BINDINGS`):

- `super+c`
- `ctrl+shift+c`
- `ctrl+insert`
- `ctrl+c`

Paste (`PromptInput.BINDINGS` + inherited TextArea):

- `ctrl+v` (inherited)
- `super+v`
- `ctrl+shift+v`
- `shift+insert`

Quit:

- `ctrl+q`

## Test Coverage

### Adapter unit tests

File: `tests/unit/terminal/default/test_clipboard.py`

Covers:

- platform command selection
- Linux wayland/x11 ordering
- backend fallback sequencing
- Windows `powershell` -> `pwsh` fallback
- paste failure (`None`) and empty-string clipboard behavior

### UI integration tests

Files:

- `tests/unit/terminal/default/test_app.py`
- `tests/unit/terminal/default/test_widgets.py`

Covers:

- copy shortcuts call app copy path and update local clipboard
- paste shortcuts (`ctrl+v`, `super+v`, `ctrl+shift+v`, `shift+insert`) use adapter result
- fallback to local clipboard when OS clipboard unavailable
- empty OS clipboard does not incorrectly reuse stale local value
- prompt paste fallback bindings are present

## Documentation Updates

Files:

- `docs/internal/architecture/terminal.md`
- `docs/cli.md`

Updates:

- document OS-first clipboard model
- document copy/paste key policy and fallback keys

### Docs guidance for user-facing behavior

- In the input field, both `Ctrl+V` and `Cmd+V` should be documented as supported paste paths.
- For copying selected text from widgets, document `Ctrl+C` as the currently reliable shortcut.
- Document `Cmd+C` as a best-effort shortcut and position `Ctrl+C` as its fallback.

## Rollback

Revert these files to remove adapter behavior:

- `freeact/terminal/default/clipboard.py`
- `freeact/terminal/default/app.py`
- `freeact/terminal/default/widgets.py`
- `tests/unit/terminal/default/test_clipboard.py`
- `tests/unit/terminal/default/test_app.py`
- `tests/unit/terminal/default/test_widgets.py`
- `docs/internal/architecture/terminal.md`
- `docs/cli.md`
