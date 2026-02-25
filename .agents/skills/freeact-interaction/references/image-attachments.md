# Image Attachments

Type `@` to open the file picker, or type `@path` directly.

## Using the file picker

```bash
# Type @ to open file picker (cursor starts at cwd)
tmux send-keys -t agent '@'
```

Wait, then navigate with `Down`/`Up`, expand dirs with `Right`, select with `Enter`. The selected path is inserted after `@`.

```bash
# Navigate to a file (e.g., 24 downs from workspace root to Burns.jpeg)
for i in $(seq 1 24); do tmux send-keys -t agent Down; sleep 0.05; done
# (separate call)
tmux send-keys -t agent Enter
```

## Typing path directly

```bash
# Type path directly (fast -l avoids triggering the picker)
tmux send-keys -t agent -l '@Burns.jpeg Describe this image'
```

Then submit in a separate call.

## Example: Image Attachment E2E

```bash
tmux new-session -d -s agent -x 120 -y 50
tmux set-option -t agent remain-on-exit on
tmux send-keys -t agent 'uv run freeact' Enter
# wait 12s for startup

# Type @ to open file picker
tmux send-keys -t agent '@'
# wait 2s, navigate to file, select with Enter

# Type question and submit
tmux send-keys -t agent -l ' Describe this image'
# (separate call)
tmux send-keys -t agent Enter
# wait 10s for response, then capture

# Cleanup
tmux send-keys -t agent C-q
sleep 2
tmux kill-session -t agent
```
