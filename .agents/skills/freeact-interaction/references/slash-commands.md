# Slash Commands (Skill Invocation)

Type `/` at the start of a prompt to open the skill picker modal.

```bash
# Type / to open skill picker
tmux send-keys -t agent '/'
```

Wait, then capture to see the picker. Navigate by typing characters to jump to the first matching skill, or use `Down`/`Up`. Select with `Enter`, cancel with `Escape`.

```bash
# Navigate to a skill by typing its prefix and select it
tmux send-keys -t agent -l 'pla'
tmux send-keys -t agent Enter
```

After selection, the prompt contains `/skill-name `. Type arguments and submit:

```bash
tmux send-keys -t agent -l 'my arguments'
# (separate call)
tmux send-keys -t agent Enter
```

## Example: Slash Command E2E

```bash
tmux new-session -d -s agent -x 120 -y 50
tmux set-option -t agent remain-on-exit on
tmux send-keys -t agent 'uv run freeact' Enter
# wait 12s for startup

# Type / to open skill picker
tmux send-keys -t agent '/'
# wait 2s, capture to verify picker

# Select first skill
tmux send-keys -t agent Enter
# wait 1s, capture to verify skill name in prompt

# Type arguments and submit
tmux send-keys -t agent -l 'my arguments'
# (separate call)
tmux send-keys -t agent Enter
# wait 10s for response, then capture

# Cleanup
tmux send-keys -t agent C-q
sleep 2
tmux kill-session -t agent
```
