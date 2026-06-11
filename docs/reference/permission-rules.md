# Permission rules

Permission rules pre-approve code actions, shell commands, and tool calls; actions without a matching rule require [interactive approval](../guides/permissions.md). Rules are stored in `.freeact/permissions.toml` as typed rules with glob-style patterns. The file is machine-managed: freeact seeds it with [default rules](#default-rules) and appends rules saved from the [approval prompt](../guides/permissions.md#save-permission-rules). It can also be edited by hand; comments do not survive the next machine write.

```toml title=".freeact/permissions.toml"
ask = [
    { tool_name = "bash", type = "ShellAction", command = "rm *" },
]
allow = [
    { tool_name = "github_*", type = "GenericCall" },
    { tool_name = "bash", type = "ShellAction", command = "git *" },
    { tool_name = "filesystem_*", path = ".freeact/**", type = "FileRead" },
    { tool_name = "filesystem_*", path = "src/**", type = "FileWrite" },
]
```

## Rule types

Each rule has a `type` field that determines which fields are matched:

| Type | Matched fields |
|------|---------------|
| `GenericCall` | `tool_name` |
| `ShellAction` | `tool_name`, `command` |
| `CodeAction` | `tool_name` |
| `FileRead` | `tool_name`, `path` |
| `FileWrite` | `tool_name`, `path` |
| `FileEdit` | `tool_name`, `path` |

`tool_name` and `command` fields support `*` (any characters) and `?` (single character). Path fields (`path`) use [path-aware matching](#path-wildcards) where `*` matches within a single directory and `**` matches across directory boundaries.

## Tiers

Permissions are organized into two tiers:

| Tier | Description |
|------|-------------|
| `allow` | Tool call executes without prompting |
| `ask` | User is always prompted for approval |

Evaluation order is **ask then allow**: if a rule matches both tiers, the user is prompted. Each tier supports two persistence scopes: **always** (persisted to `permissions.toml`) and **session** (in-memory, cleared when the session ends).

## Tool call patterns

Tool call patterns match against MCP tool names (e.g. `github_search_repositories`, `filesystem_read_text_file`). Filesystem tools (`FileRead`, `FileWrite`, `FileEdit`) additionally match on path fields, enabling path-specific rules like allowing reads only from `src/**`.

## Shell command patterns

`ShellAction` rules match on `tool_name` (`bash` for `!` commands, `shell_magic` for `%%bash` scripts) and `command`. The `command` field supports glob matching with `*` and `?`. Shell commands are intercepted during code execution with Python variables fully resolved, so patterns match against the actual command values.

| Pattern | Matches |
|---------|---------|
| `git *` | Any `git` command |
| `git commit *` | `git commit` with any arguments |
| `pip install *` | `pip install` with any package |
| `rm *` | Any `rm` command (use in `ask` tier to always prompt) |

Composite shell commands joined with `&&`, `||`, `|`, or `;` are decomposed into individual sub-commands, each checked independently. If any sub-command is denied, the entire command is blocked.

## Path wildcards

Path fields (`path`) in `FileRead`, `FileWrite`, and `FileEdit` rules use path-aware matching. Paths are normalized relative to the working directory before matching: absolute paths under the working directory become relative, paths outside stay absolute.

| Wildcard | Scope |
|----------|-------|
| `*` | Matches within a single directory |
| `**` | Matches across directory boundaries |

The leading `/` determines whether a pattern targets paths inside or outside the working directory:

| Pattern | Inside working dir | Outside working dir |
|---------|--------------------|---------------------|
| `**` | Yes | No |
| `/**` | No | Yes |
| `src/**` | Yes (under `src/`) | No |

`tool_name` and `command` fields use standard glob matching where `*` matches any characters and `?` matches a single character.

## Default rules

On first run, `permissions.toml` is seeded with a generous set of read-only allow rules (file reads inside the working directory, common shell inspection commands like `ls`, `cat`, `git status`, and read-only built-in tools) plus an ask rule that always prompts for `.env` reads. Inspect `.freeact/permissions.toml` after the first run for the full list, and edit it to tighten or extend the defaults.
