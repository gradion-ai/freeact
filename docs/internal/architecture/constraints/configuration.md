# Configuration Constraints

Configuration flows one way: file -> schema -> resolve. There is no programmatic "save config" API.

## Parse, then resolve

| Module | Job | Allowed effects |
|---|---|---|
| `freeact/config/schema.py` | Pydantic models mirroring `.freeact/config.toml` (`FreeactConfig` with `agent`/`terminal` sections, `ToolPresets`) | None: pure data, frozen, `extra="forbid"`. No I/O, no env access, no model instantiation. |
| `freeact/config/load.py` | `load(working_dir)` reads/validates `config.toml` (missing file -> defaults); `init(working_dir)` initializes the workspace; `Workspace` defines all filesystem paths | File reads in `load`; writes only in `init`. |
| `freeact/config/resolve.py` | `resolve(config, working_dir, env) -> ResolvedRuntime` | Reads `env` (defaults to `os.environ`), instantiates the pydantic-ai model when `provider_settings` is set. |

Invariants:

- `schema.py` stays pure data. No `model_post_init` resolution, no `object.__setattr__` workarounds anywhere; if a value depends on the environment, it belongs in `resolve.py`.
- `config.toml` is human-owned. It is written exactly once by `init()` (commented defaults, `DEFAULT_CONFIG_TOML`) and never rewritten by the app. `init()` also creates runtime dirs (`generated/`, `plans/`, `sessions/`) and materializes bundled skills without overwriting existing skill directories (`freeact/config/skills.py`).
- Permissions are NOT in `config.toml`; they live in the machine-managed `.freeact/permissions.toml` (see [permissions.md](permissions.md)). `config/` does not depend on `permissions.py`; `cli.py` wires both.

## Resolution semantics (`resolve.py`)

- Tool presets (`[agent.tools]`: `search`, `fetch`, `discovery = "basic" | "hybrid"`) expand into internal server configs here: `filesystem` and optional `pytools` MCP servers, `google`/`fetch` PTC servers. User-defined `mcp_servers`/`ptc_servers` are merged over internals.
- `${VAR}` substitution (via `mcpygen.vars.replace_variables`) happens at resolve; a missing variable raises `ValueError` naming the variable. Exception: `ptc_servers` are validated at resolve but returned unsubstituted (substitution happens at use: API generation / server start).
- Kernel env: `PYTHONPATH` always contains the generated dir; `HOME` is inherited from the host env unless the user sets it; user `kernel_env` entries are `${VAR}`-substituted.
- `discovery = "hybrid"` without the `freeact[search]` extra fails at resolve with an install hint (`_require_hybrid_extra`).
- `0` sentinels: `execution_timeout = 0` disables the timeout, `approval_timeout = 0` waits forever (`ResolvedRuntime` properties map `0` to `None`).
- `ResolvedRuntime.for_subagent()` derives the child runtime: deep-copied servers with `PYTOOLS_SYNC`/`PYTOOLS_WATCH` forced off, copied `kernel_env`, `enable_subagents=False`, `subagent_mode=True`.

## Paths via Workspace

All `.freeact/` layout knowledge lives in `Workspace` (`freeact/config/load.py`): `config_file`, `skills_dir`, `plans_dir`, `generated_dir`, `sessions_dir`, `search_db_file`, `project_instructions_file` (`AGENTS.md`), `project_skills_dir` (`.agents/skills`), `images_dir(configured)`. Do not hardcode `.freeact/...` paths elsewhere; derive them from `Workspace`.

TOML I/O: stdlib `tomllib` for reads. `tomli-w` is used only for `permissions.toml`; the init-time `config.toml` is written as the literal commented template `DEFAULT_CONFIG_TOML` (a TOML writer cannot emit comments).
