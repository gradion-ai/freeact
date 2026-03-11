# Configuration Constraints

Agent config and terminal config follow the same structural pattern:

| Aspect | Agent Config | Terminal Config |
|---|---|---|
| Class | `Config` in `freeact/agent/config/config.py` | `Config` in `freeact/terminal/config.py` |
| Storage | `.freeact/agent.json` | `.freeact/terminal.json` |
| `model_post_init` | Resolves model, MCP servers, kernel env | Resolves `working_dir` |
| `init()` classmethod | Load if `.freeact/` exists, else save defaults | Load if file exists, else save defaults |
| `load()` classmethod | Read JSON, `model_validate` with `working_dir` | Same pattern |
| `save()` async method | Delegates to `_save_sync` via `arun()` | Same pattern |
| `_save_sync` | `model_dump(mode="json", exclude={"working_dir"})` | Same pattern |
| `working_dir` field | `Field(default_factory=Path.cwd, exclude=True)` | Same pattern |
| Frozen | Yes | Yes |

When adding a new config domain, follow this same pattern: frozen Pydantic model, `init`/`load`/`save` classmethods, `_save_sync` for the sync core, `working_dir` excluded from serialization.
