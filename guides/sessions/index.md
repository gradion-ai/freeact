# Persist and resume sessions

The `enable_persistence` setting in the [`[agent]` section](https://gradion-ai.github.io/freeact/reference/configuration/#agent-settings) of `.freeact/config.toml` controls session persistence.

- Default: `true`. The agent persists history to `.freeact/sessions/<session-id>/<agent-id>.jsonl`.
- `false`: The agent keeps history in memory only. Passing `session_id` to Agent raises `ValueError`.

## Create a session

When persistence is enabled, construct an agent without `session_id` to create a new session ID internally. Read it from `agent.session_id`:

```
# No session_id: agent creates a new session ID internally.
async with Agent(runtime) as agent:
    print(f"Generated session ID: {agent.session_id}")
    await handle_events(agent, "What is the capital of France?")
    await handle_events(agent, "What about Germany?")
```

## Resume a session

Construct an agent with an explicit `session_id` for create-or-resume behavior:

```
# Choose an explicit session ID.
session_id = "countries-session"
# Create-or-resume behavior: resume if present, otherwise start new.
async with Agent(runtime, session_id=session_id) as agent:
    await handle_events(agent, "What is the capital of Spain?")
```

If that `session_id` already exists, the persisted history is resumed. If it does not exist, a new session starts with that ID.

To resume later, create another agent with the same `session_id`:

```
# Resume the same session ID later.
async with Agent(runtime, session_id=session_id) as agent:
    # Previous message history is restored automatically
    await handle_events(agent, "And what country did we discuss in this session?")
```

Only the main agent's message history (`main.jsonl`) is loaded on resume. Subagent messages are persisted to separate files (`sub-xxxx.jsonl`) for auditing but are not rehydrated.

## Resume from the CLI

The [CLI tool](https://gradion-ai.github.io/freeact/reference/cli/index.md) accepts `--session-id` to resume a session from the command line when `enable_persistence` is `true`:

```
freeact --session-id 550e8400-e29b-41d4-a716-446655440000
```

If `enable_persistence` is `false` in `.freeact/config.toml`, passing `--session-id` exits with an error.

## Large tool results

Tool call results, code execution outputs, and subagent responses are checked against an inline size threshold before being added to the message history. When a result exceeds the threshold, the full content is saved to `.freeact/sessions/<session-id>/tool-results/` and replaced inline with a file reference notice that includes a preview. This prevents large outputs from bloating context.

Controlled by two [config options](https://gradion-ai.github.io/freeact/reference/configuration/#agent-settings):

- `tool_result_inline_max_bytes`: Maximum inline payload size in bytes.
- `tool_result_preview_chars`: Number of preview characters from both the beginning and end of large text results included in the file reference notice.
