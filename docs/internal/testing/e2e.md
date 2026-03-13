# End-to-End Testing

E2E tests use the `freeact-interaction` skill to drive freeact through tmux.

## Setup

- Always check for `.freeact/` first. It is not checked into git.
- If missing (worktrees, fresh clones), create it with `uv run freeact init`.
- Edit `.freeact/agent.json` as needed for the test scenario (e.g. adding a PTC server entry).
- API keys live in the repo's `.env` file. Freeact loads it automatically via `dotenv` on startup. The `${VAR}` references in `agent.json` resolve from this environment.

## Verification

- Agent completes the requested task without errors.
- No errors in scrollback (`tmux capture-pane -t agent -p -S -100`).

## PTC server testing

- Add the server entry to `ptc_servers` in `.freeact/agent.json`.
- Send a prompt that explicitly names the tool under test.
- Approve tool executions when prompted (code action, then PTC call).
- Verify the agent response is grounded in real data from the external API.
