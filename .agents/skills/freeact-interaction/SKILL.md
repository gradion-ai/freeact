---
name: freeact-interaction
description: Interact with freeact agent via tmux for testing
---

# Interacting with Freeact via tmux

Freeact's terminal UI (Textual) requires a real TTY. Use tmux to provide a pseudo-TTY.

## Setup

```bash
# Start detached tmux session (120x50 recommended for proper rendering)
tmux new-session -d -s agent -x 120 -y 50
tmux set-option -t agent remain-on-exit on

# Start freeact (do NOT redirect stderr, it breaks Textual's terminal detection)
tmux send-keys -t agent 'uv run freeact' Enter
```

Wait at least 10 seconds for startup (MCP servers need to initialize).

## Capturing Output

Textual renders to the terminal's alternate screen buffer. `tmux capture-pane` captures it correctly as long as stderr is not redirected.

```bash
# Capture visible screen
tmux capture-pane -t agent -p

# Capture with scrollback
tmux capture-pane -t agent -p -S -50
```

## Sending Input

Use separate tool calls for sending keys and capturing output. Never chain `tmux send-keys` and `tmux capture-pane` in a single bash command -- the shell command text leaks into the Textual prompt.

```bash
# Send literal text (use -l to avoid key interpretation)
tmux send-keys -t agent -l 'your message here'
```

Then in a separate call:

```bash
tmux send-keys -t agent Enter
```

Then wait and capture in another separate call.

## Approval Prompt

```bash
# Approve: y, Reject: n, Always: a, Session: s
tmux send-keys -t agent 'y'
```

## Quit and Cleanup

```bash
tmux send-keys -t agent C-q
sleep 2
tmux kill-session -t agent
```

## Additional guides

- [Slash commands](references/slash-commands.md) - Testing `/skill-name` invocation via the skill picker
- [Image attachments](references/image-attachments.md) - Testing `@path` image attachments via the file picker
