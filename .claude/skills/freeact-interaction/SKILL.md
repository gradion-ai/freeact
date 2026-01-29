---
name: freeact-interaction
description: Interact with freeact agent via tmux for testing and recording sessions
---

# Interacting with Freeact via tmux

Freeact's terminal interface uses prompt_toolkit which requires a real TTY. Use tmux to provide a pseudo-TTY.

## Setup

```bash
# Start detached tmux session (120x50 recommended for proper rendering)
tmux new-session -d -s agent -x 120 -y 50

# Start freeact (with optional recording)
tmux send-keys -t agent 'uv run freeact' Enter
# Or with recording:
tmux send-keys -t agent 'uv run freeact --record' Enter
```

## Interaction Loop

```bash
# Wait for startup/response (adjust sleep as needed)
sleep 3

# Capture current screen (-S -N for N lines of scrollback)
tmux capture-pane -t agent -p -S -50

# Send user input
tmux send-keys -t agent 'your message here' Enter

# Approve code execution
tmux send-keys -t agent 'Y' Enter
```

## Important Notes

- **Double echo**: When recording (`--record`), input appears twice - this is expected behavior for capturing input in the Rich console recording
- **Timing**: Wait between sends for the agent to respond before sending next input
- **Approval options**: Y (yes), n (no), a (always), s (session)
- **Quit**: Send `q` to exit freeact cleanly

## Recording Output

- Default output directory: `output/`
- Creates: `conversation.svg` and `conversation.html`
- Custom directory: `--record-dir PATH`
- Custom title: `--record-title "Title"`

## Cleanup

```bash
# Kill the tmux session when done
tmux kill-session -t agent
```

## Example Full Session

```bash
# Setup
tmux new-session -d -s agent -x 120 -y 50
tmux send-keys -t agent 'uv run freeact --record' Enter
sleep 3

# Send query
tmux send-keys -t agent 'What is 2 + 2?' Enter
sleep 5
tmux capture-pane -t agent -p -S -50

# Approve execution
tmux send-keys -t agent 'Y' Enter
sleep 3
tmux capture-pane -t agent -p -S -30

# Quit and cleanup
tmux send-keys -t agent 'q' Enter
sleep 2
tmux kill-session -t agent

# Recording saved to output/conversation.{svg,html}
```
