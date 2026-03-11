# Configuration Constraints

## PersistentConfig base class

`PersistentConfig` (`freeact/config.py`) is the base class for all JSON-persisted configuration models. It provides the persistence lifecycle:

| Aspect | PersistentConfig |
|---|---|
| `working_dir` field | `Field(default_factory=Path.cwd, exclude=True)` |
| `model_post_init` | Resolves `working_dir` to absolute path |
| `freeact_dir` property | `working_dir / ".freeact"` |
| `_config_file` property | `freeact_dir / _config_filename` |
| `init()` classmethod | Load if config file exists, else save defaults |
| `load()` classmethod | Read JSON, `model_validate` with `working_dir` |
| `save()` async method | Delegates to `_save_sync` via `arun()` |
| `_save_sync` | `model_dump(mode="json", exclude={"working_dir"})` |
| Frozen | Yes (`ConfigDict(frozen=True, extra="forbid", validate_assignment=True)`) |

## Subclass overrides

Subclasses set `_config_filename` (a `ClassVar[str]`) and may override:

- `model_post_init` -- call `super().model_post_init(__context)` first, then add domain-specific resolution.
- `_save_sync` -- call `super()._save_sync()` first, then create additional directories or materialize assets.

| Subclass | File | `_config_filename` | `model_post_init` override | `_save_sync` override |
|---|---|---|---|---|
| Agent `Config` | `freeact/agent/config/config.py` | `"agent.json"` | Resolves model, MCP servers, kernel env | Validates model is str, creates dirs, materializes skills |
| Terminal `Config` | `freeact/terminal/config.py` | `"terminal.json"` | None (base is sufficient) | None (base is sufficient) |

Agent `Config` adds `ConfigDict(arbitrary_types_allowed=True)` which Pydantic merges with the parent's `ConfigDict`.

When adding a new config domain, inherit from `PersistentConfig`, set `_config_filename`, and override `model_post_init` / `_save_sync` only if needed.
