## freeact.permissions.PermissionManager

```
PermissionManager(
    working_dir: Path | None = None,
    freeact_dir: Path = Path(".freeact"),
)
```

Tool call permission gating with type-specific pattern rules.

Rules are `ToolCall` instances whose fields may contain glob wildcards (`*`, `?`). Path fields (`path`, `paths`) use path-aware matching where `*` matches within a single directory and `**` matches across directory boundaries. Non-path fields (`tool_name`, `command`) use simple glob matching.

Use allow_always and allow_session to store pattern rules. Use is_allowed to check concrete (no wildcards) tool calls against stored rules.

Evaluation order: ask-session, ask-always, allow-session, allow-always. First match wins. Ask takes priority over allow.

### allow_always

```
allow_always(tool_call: ToolCall) -> None
```

Add a pattern rule to the always-allow list and persist.

The tool call's fields may contain glob wildcards. For example, `ShellAction(tool_name="bash", command="git *")` allows all git subcommands, and `FileRead(tool_name="filesystem_*", paths=("src/**",))` allows reading any file under `src/`.

### allow_session

```
allow_session(tool_call: ToolCall) -> None
```

Add a pattern rule to the session-allow list (not persisted).

The tool call's fields may contain glob wildcards, same as allow_always. Session rules are cleared when the process ends.

### init

```
init() -> None
```

Load permissions when present, otherwise save defaults.

### is_allowed

```
is_allowed(tool_call: ToolCall) -> bool
```

Check if a concrete tool call is pre-approved.

The tool call should contain literal values (no wildcards). Its fields are matched against the glob patterns in stored rules.

Parameters:

| Name        | Type       | Description                  | Default    |
| ----------- | ---------- | ---------------------------- | ---------- |
| `tool_call` | `ToolCall` | Concrete tool call to check. | *required* |

Returns:

| Type   | Description                                         |
| ------ | --------------------------------------------------- |
| `bool` | True if an allow rule matches and no ask rule takes |
| `bool` | precedence, False otherwise.                        |

### load

```
load() -> None
```

Load permissions from `.freeact/permissions.json`.

### save

```
save() -> None
```

Persist always-tier permissions to `.freeact/permissions.json`.
