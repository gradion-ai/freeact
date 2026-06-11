# Manage permissions

Every code action, shell command, and tool call requires user approval before execution, unless it is pre-approved by a permission rule. This guide shows how to respond to approval prompts in the CLI, save and edit permission rules, bypass permission checks, and automate approvals in SDK applications. For rule syntax and matching semantics, see [Permission rules](../reference/permission-rules.md). For the approval model itself, see [Approvals and permissions](../concepts/approvals.md).

## Respond to approval prompts

Before executing code actions, shell commands, and tool calls, the agent requests approval. Shell commands and programmatic tool calls within code actions are intercepted during execution and approved individually. For shell commands the prompt displays the verbatim command being executed; for other action types it displays a suggested permission pattern that summarizes the action:

```
Approve? [Y/n/a/s] git add src/main.py
```

| Key | Action |
|-----|--------|
| `y` / `Enter` | Approve this invocation only |
| `n` | Reject (ends the current agent turn) |
| `a` | Edit pattern, then save as always-allow rule |
| `s` | Edit pattern, then save as session-allow rule |

What the bar displays depends on the action type:

| Action | Bar shows | Suggested pattern (when pressing `a`/`s`) |
|--------|-----------|-------------------------------------------|
| Shell command (`!cmd` and split sub-commands) | Verbatim command, e.g. `git add src/main.py` | `cmd subcmd *` heuristic, e.g. `git add *` |
| Shell magic (`%%bash`) | First non-empty line + `(+N more lines)` summary; full script is shown in the Shell Script box above the bar | Full script with newlines escaped as `\n` |
| Code action | Tool name, e.g. `ipybox_execute_ipython_cell` | Same |
| File read/write/edit | Tool name + path, e.g. `filesystem_write_text_file src/main.py` | Same |
| Other tool calls | Tool name, e.g. `github_search_repositories` | Same |

## Save permission rules

Pressing `a` or `s` opens an editable input pre-filled with the suggested permission pattern (not the verbatim text shown in the bar). Edit the pattern to broaden or narrow the rule (e.g. change `filesystem_read_text_file src/main.py` to `filesystem_* src/**`), then press `Enter` to save the rule and approve. While editing, approval hotkeys are disabled so you can type freely.

For shell commands, the pre-filled pattern heuristic uses `cmd subcmd *` for known multi-word tools (git, pip, docker, kubectl, npm, uv, cargo, etc.) and `cmd *` for others.

Always-allow rules persist to `.freeact/permissions.toml` across sessions. Session-allow rules are in-memory and cleared when the session ends. Future actions matching a saved rule are auto-approved without prompting.

## Edit permission rules

Rules are stored in `.freeact/permissions.toml` as typed rules with glob-style patterns. The file is machine-managed: freeact seeds it with [default rules](../reference/permission-rules.md#default-rules) and appends rules saved from the approval prompt. It can also be edited by hand; comments do not survive the next machine write.

```toml title=".freeact/permissions.toml"
ask = [
    { tool_name = "bash", type = "ShellAction", command = "rm *" },
]
allow = [
    { tool_name = "bash", type = "ShellAction", command = "git *" },
]
```

Rules in the `ask` tier always prompt, even when an `allow` rule also matches. Inspect the file after the first run for the seeded defaults, and edit it to tighten or extend them. See [Permission rules](../reference/permission-rules.md) for rule types, pattern syntax, matching semantics, and a fuller example.

## Skip permission checks

The CLI supports a [`--skip-permissions`](../reference/cli.md#options) flag to run tools without prompting for approval, effectively auto-approving all actions:

```bash
freeact --skip-permissions
```

## Automate approvals in SDK applications

The agent does not enforce permissions itself. It yields [`ApprovalRequest`][freeact.ApprovalRequest] events and leaves the decision to the application. [`PermissionManager`][freeact.PermissionManager] is an optional utility that applications can use to automate those decisions based on stored rules. The [CLI tool](../reference/cli.md) uses it internally; SDK applications can use it the same way.

The manager loads and saves rules from `.freeact/permissions.toml`. Rules are typed, glob-style [patterns](../reference/permission-rules.md) organized into two tiers (allow and ask) and two persistence scopes (always and session).

The core API:

- [`init()`][freeact.permissions.PermissionManager.init] loads rules from `.freeact/permissions.toml` if present, otherwise saves defaults.
- [`is_allowed(tool_call)`][freeact.permissions.PermissionManager.is_allowed] checks a concrete tool call (literal values, no wildcards) against stored rules.
- [`allow_always(tool_call)`][freeact.permissions.PermissionManager.allow_always] adds a rule and persists it to `permissions.toml`. The tool call fields may contain glob wildcards to match broadly (e.g., `command="git *"`).
- [`allow_session(tool_call)`][freeact.permissions.PermissionManager.allow_session] adds an in-memory rule for the current session. Same wildcard support as `allow_always`.

```python
import asyncio
from freeact import ApprovalRequest, PermissionManager, suggest_pattern

loop = asyncio.get_running_loop()

manager = PermissionManager()
await loop.run_in_executor(None, manager.init)

async for event in agent.stream(prompt):
    match event:
        case ApprovalRequest() as request:
            if manager.is_allowed(request.tool_call):
                request.approve(True)
            else:
                pattern = suggest_pattern(request.tool_call)
                choice = input(f"Allow [{pattern}]? [Y/n/a/s]: ")
                match choice:
                    case "a":
                        await loop.run_in_executor(
                            None, 
                            manager.allow_always, 
                            request.tool_call,
                        )
                        request.approve(True)
                    case "s":
                        manager.allow_session(request.tool_call)
                        request.approve(True)
                    case "n":
                        request.approve(False)
                    case _:
                        request.approve(True)
```

For shell commands, [`suggest_display(tool_call)`][freeact.suggest_display] returns the verbatim command (or a first-line summary for `%%bash` shell magic) and is suitable for displaying in the prompt instead of the permission pattern. It returns an empty string for non-shell tool calls, so applications can fall back to `suggest_pattern()` in that case.
