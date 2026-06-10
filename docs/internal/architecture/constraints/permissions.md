# Permission System Constraints

Rules are typed pydantic classes in `freeact/permissions.py`, one per ToolCall type, forming the `PermissionRule` discriminated union (`type` field): `GenericCallRule`, `ShellActionRule` (tool name + command globs), `CodeActionRule`, `FileReadRule`/`FileWriteRule`/`FileEditRule` (tool name glob + path pattern). Each rule owns `matches(call, working_dir)`; rules match only their own ToolCall type. `rule_from_call(tool_call)` builds a rule from a (possibly wildcarded) tool call; it is the only conversion path.

## Evaluation order (INVARIANT)

`PermissionManager._check_all`: session-ask, always-ask, session-allow, always-allow. First match wins; ask beats allow; no match means not allowed (explicit allow required).

## Path security (INVARIANTs, preserve exactly)

- `_normalize_path`: absolute paths under `working_dir` become relative before matching; paths outside stay absolute.
- `_path_matches`: pattern and path must agree on absoluteness; a relative pattern (including bare `**`) NEVER matches an absolute path. This is what keeps the broad `**` read-allow from exposing `/etc/passwd` or `~/.ssh/...`.
- Path matching uses `PurePosixPath.full_match` (`*` does not cross `/`, `**` crosses any depth). Non-path fields use `fnmatch`.
- `**/.env` is in `DEFAULT_ASK_RULES` and beats the `**` allow.

## Defaults rationale

`DEFAULT_ALLOW_RULES`: file reads (`**`) for `filesystem_*` tools, pytools introspection (`pytools_list_categories/list_tools/search_tools`), and a curated read-only shell list (introspection, listing/metadata, text reading, process info, git read-only subcommands). Deliberately excluded: mutating git commands, `find`/`env` (can execute arbitrary commands), `rm/mv/cp/...`, and everything via `shell_magic` (no shell_magic defaults at all). fnmatch nuance: `git status *` does not match bare `git status`, so non-trivial commands need both entries; `git tag`/`git branch`/`git reflog` get only the bare form because the `*` form would match destructive flags.

## Storage

`.freeact/permissions.toml` is machine-managed (written with `tomli_w`); never hand-maintain comments there, and never store permissions in `config.toml`. `PermissionManager.init()` loads the file when present, else saves defaults; the constructor creates no directories (only `save()` does). Always-tier rules persist; session-tier rules are memory-only; adds deduplicate. Seeding is the embedder's job (`cli.py` calls `init()`).

## Adding a new ToolCall subtype

| Location | Change |
|---|---|
| `freeact/toolcalls.py` | Subclass + `from_raw()` match arm + `to_pattern`/`to_display` (optional)/`from_pattern` overrides |
| `freeact/permissions.py` | Rule class with `matches()`, added to the `PermissionRule` union and a `rule_from_call()` arm |
| `freeact/terminal/approvals.py` | Renderer entry in `_RENDERERS` |
