## freeact.permissions.PermissionManager

```
PermissionManager(freeact_dir: Path = Path('.freeact'))
```

Tool permission gating with two-tier approval: always-allowed (persisted) and session-only (in-memory).

Filesystem tools targeting paths within `.freeact/` are auto-approved without explicit permission grants.

### allow_always

```
allow_always(tool_name: str) -> None
```

Grant permanent permission for a tool and persist to disk.

### allow_session

```
allow_session(tool_name: str) -> None
```

Grant permission for a tool until the session ends (not persisted).

### is_allowed

```
is_allowed(
    tool_name: str, tool_args: dict[str, Any] | None = None
) -> bool
```

Check if a tool call is pre-approved.

Returns `True` if the tool is in the always-allowed or session-allowed set, or if it's a filesystem tool operating within `.freeact/`.

### load

```
load() -> None
```

Load always-allowed tools from `.freeact/permissions.json`.

### save

```
save() -> None
```

Persist always-allowed tools to `.freeact/permissions.json`.
