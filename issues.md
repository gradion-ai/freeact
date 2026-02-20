# Clipboard Issues and Solutions (Terminal UI)

This document explains when copy/paste works, when it can still fail, and why.

## Current Implementation

The default terminal UI uses an OS-first clipboard adapter:

- Copy: selected text is written to the OS clipboard first, then mirrored to Textual local clipboard (`app.clipboard`).
- Paste (prompt input): reads OS clipboard first, falls back to Textual local clipboard when OS access fails.

Platform backends:

- macOS: `pbcopy` / `pbpaste`
- Linux: `wl-copy` / `wl-paste` (Wayland), then `xclip` / `xsel` fallbacks
- Windows: PowerShell (`powershell`, then `pwsh` fallback)

## Why This Exists

Textual's default clipboard path depends on terminal support and key forwarding behavior (for example OSC 52 and `Cmd` key delivery). That can be inconsistent across terminals and session types.

The adapter avoids most of that by using native OS clipboard commands directly.

## Expected Behavior by Terminal

### macOS Terminal.app

- `Cmd` keys may still be intercepted by Terminal.app before the TUI sees them.
- Even if `Cmd` is intercepted, copy/paste can still work via fallback keys because the app now uses OS clipboard commands.

Recommended keys:

- Copy: `Ctrl+C`, `Ctrl+Shift+C`, `Ctrl+Insert`
- Paste: `Ctrl+V`, `Ctrl+Shift+V`, `Shift+Insert`

### iTerm2

- Usually better `Cmd` forwarding than Terminal.app.
- With adapter mode, clipboard sync should be reliable even when `Cmd` forwarding is imperfect.

Recommended keys:

- Copy: `Cmd+C` (if forwarded) or fallback copy keys
- Paste: `Cmd+V` (if forwarded) or fallback paste keys

### Other modern terminals (kitty, WezTerm, etc.)

- Generally good behavior.
- Adapter still helps when terminal key routing or clipboard integration differs by config.

## Remaining Failure Cases

### Missing OS clipboard tools

Linux systems may lack `wl-copy`, `xclip`, and `xsel`.

Result:

- App falls back to Textual local clipboard only.

### Remote/tmux/screen sessions

Clipboard behavior can still vary based on process environment and available commands on the executing host.

Result:

- OS clipboard access may not target the machine the user expects.

### Key forwarding conflicts

Terminal-level shortcuts can still override app-level shortcuts.

Result:

- A particular shortcut may not trigger the app action even though clipboard commands are configured correctly.

## User Guidance for Docs

1. Explain that the app is OS-clipboard-first with local fallback.
2. List both `Cmd` and fallback `Ctrl`/`Insert` shortcuts.
3. Call out that terminal settings can intercept `Cmd` shortcuts.
4. For Linux, document that `wl-copy`, `xclip`, or `xsel` may be required.
5. Mention that remote/tmux environments can change clipboard behavior.
