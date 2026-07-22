## freeact.config.load

### Workspace

```
Workspace(working_dir: Path)
```

Filesystem layout of a freeact workspace.

### init

```
init(working_dir: Path | None = None) -> FreeactConfig
```

Initialize a workspace: write default config if missing, create runtime dirs.

Writes the commented default `config.toml` when none exists (never overwrites), creates the runtime directories, and materializes bundled skills without overwriting user-modified ones.

Parameters:

| Name          | Type   | Description | Default                                            |
| ------------- | ------ | ----------- | -------------------------------------------------- |
| `working_dir` | \`Path | None\`      | Workspace root; defaults to the current directory. |

Returns:

| Type            | Description                                       |
| --------------- | ------------------------------------------------- |
| `FreeactConfig` | The effective configuration after initialization. |

### load

```
load(working_dir: Path | None = None) -> FreeactConfig
```

Load `.freeact/config.toml`, returning defaults when missing.

Parameters:

| Name          | Type   | Description | Default                                            |
| ------------- | ------ | ----------- | -------------------------------------------------- |
| `working_dir` | \`Path | None\`      | Workspace root; defaults to the current directory. |

Returns:

| Type            | Description                                         |
| --------------- | --------------------------------------------------- |
| `FreeactConfig` | Parsed configuration (pure data, nothing resolved). |

### workspace

```
workspace(working_dir: Path | None = None) -> Workspace
```

Create a Workspace for a working directory.

Parameters:

| Name          | Type   | Description | Default                                            |
| ------------- | ------ | ----------- | -------------------------------------------------- |
| `working_dir` | \`Path | None\`      | Workspace root; defaults to the current directory. |

Returns:

| Type        | Description                        |
| ----------- | ---------------------------------- |
| `Workspace` | Workspace with resolved root path. |

## freeact.config.init

```
init(working_dir: Path | None = None) -> FreeactConfig
```

Initialize a workspace: write default config if missing, create runtime dirs.

Writes the commented default `config.toml` when none exists (never overwrites), creates the runtime directories, and materializes bundled skills without overwriting user-modified ones.

Parameters:

| Name          | Type   | Description | Default                                            |
| ------------- | ------ | ----------- | -------------------------------------------------- |
| `working_dir` | \`Path | None\`      | Workspace root; defaults to the current directory. |

Returns:

| Type            | Description                                       |
| --------------- | ------------------------------------------------- |
| `FreeactConfig` | The effective configuration after initialization. |

## freeact.config.resolve

### ResolvedRuntime

```
ResolvedRuntime(
    config: AgentSection,
    workspace: Workspace,
    model: str | Model,
    mcp_servers: dict[str, dict[str, Any]],
    ptc_servers: dict[str, dict[str, Any]],
    kernel_env: dict[str, str],
    enable_subagents: bool,
    subagent_mode: bool = False,
)
```

Everything the agent needs at runtime, resolved from config + environment.

Produced by resolve(). Unlike FreeactConfig, values here are concrete: `${VAR}` references substituted, presets expanded into server configs, and the model ready for pydantic-ai.

#### for_subagent

```
for_subagent() -> ResolvedRuntime
```

Derive the runtime for a subagent.

Subagents cannot nest, and in hybrid discovery mode they neither sync nor watch the shared search index.

### resolve

```
resolve(
    config: FreeactConfig,
    working_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> ResolvedRuntime
```

Resolve a parsed config against the environment into runtime values.

Expands tool presets into server configs, substitutes `${VAR}` references (missing variables raise `ValueError` naming the variable), instantiates the model when provider settings are present, and computes the kernel environment.

Parameters:

| Name          | Type                | Description           | Default                                                      |
| ------------- | ------------------- | --------------------- | ------------------------------------------------------------ |
| `config`      | `FreeactConfig`     | Parsed configuration. | *required*                                                   |
| `working_dir` | \`Path              | None\`                | Workspace root; defaults to the current directory.           |
| `env`         | \`Mapping[str, str] | None\`                | Environment for ${VAR} substitution; defaults to os.environ. |

Returns:

| Type              | Description              |
| ----------------- | ------------------------ |
| `ResolvedRuntime` | Resolved runtime values. |

## freeact.config.workspace

```
workspace(working_dir: Path | None = None) -> Workspace
```

Create a Workspace for a working directory.

Parameters:

| Name          | Type   | Description | Default                                            |
| ------------- | ------ | ----------- | -------------------------------------------------- |
| `working_dir` | \`Path | None\`      | Workspace root; defaults to the current directory. |

Returns:

| Type        | Description                        |
| ----------- | ---------------------------------- |
| `Workspace` | Workspace with resolved root path. |

## freeact.config.FreeactConfig

Bases: `BaseModel`

Root configuration model mirroring `.freeact/config.toml`.

Config:

- `extra`: `forbid`
- `frozen`: `True`

Fields:

- `agent` (`AgentSection`)
- `terminal` (`TerminalSection`)

## freeact.config.AgentSection

Bases: `BaseModel`

Agent configuration (`[agent]`). Pure data; resolution is separate.

Config:

- `extra`: `forbid`
- `frozen`: `True`

Fields:

- `model` (`str`)
- `model_settings` (`dict[str, Any]`)
- `provider_settings` (`dict[str, Any] | None`)
- `tools` (`ToolPresets`)
- `execution_timeout` (`float`)
- `approval_timeout` (`float`)
- `tool_result_inline_max_bytes` (`int`)
- `tool_result_preview_chars` (`int`)
- `enable_persistence` (`bool`)
- `enable_subagents` (`bool`)
- `max_subagents` (`int`)
- `images_dir` (`Path | None`)
- `kernel_env` (`dict[str, str]`)
- `mcp_servers` (`dict[str, dict[str, Any]]`)
- `ptc_servers` (`dict[str, dict[str, Any]]`)

### approval_timeout

```
approval_timeout: float = 0
```

Approval wait timeout in seconds; `0` waits forever.

### execution_timeout

```
execution_timeout: float = 300
```

Code execution timeout in seconds; `0` disables the timeout.

### mcp_servers

```
mcp_servers: dict[str, dict[str, Any]]
```

User-defined MCP servers for JSON tool calling.

### ptc_servers

```
ptc_servers: dict[str, dict[str, Any]]
```

User-defined MCP servers for programmatic tool calling (code mode).

## freeact.config.ToolPresets

Bases: `BaseModel`

One-line opt-ins for bundled tool servers (`[agent.tools]`).

Minimal defaults: everything is off except the built-ins code actions require (code execution and filesystem, which are always on).

Config:

- `extra`: `forbid`
- `frozen`: `True`

Fields:

- `search` (`bool`)
- `fetch` (`bool`)
- `discovery` (`Literal['basic', 'hybrid', 'off']`)

### discovery

```
discovery: Literal['basic', 'hybrid', 'off'] = 'basic'
```

Tool discovery mode. `"hybrid"` needs the `freeact[search]` extra.

Defaults to `"basic"`: without a discovery server the agent cannot enumerate its generated tool APIs and falls back to ad-hoc code.

### fetch

```
fetch: bool = False
```

Web fetch (code mode).

### search

```
search: bool = False
```

Google search via Gemini grounding (code mode). Needs `GEMINI_API_KEY`.

## freeact.config.TerminalSection

Bases: `BaseModel`

Terminal UI configuration (`[terminal]`).

Config:

- `extra`: `forbid`
- `frozen`: `True`

Fields:

- `collapse_thoughts_on_complete` (`bool`)
- `collapse_exec_output_on_complete` (`bool`)
- `collapse_approved_code_actions` (`bool`)
- `collapse_approved_tool_calls` (`bool`)
- `collapse_completed_subagent_tasks` (`bool`)
- `collapse_tool_outputs` (`bool`)
- `keep_rejected_actions_expanded` (`bool`)
- `pin_pending_approval_action_expanded` (`bool`)
- `expand_all_toggle_key` (`str`)

## freeact.config.ResolvedRuntime

```
ResolvedRuntime(
    config: AgentSection,
    workspace: Workspace,
    model: str | Model,
    mcp_servers: dict[str, dict[str, Any]],
    ptc_servers: dict[str, dict[str, Any]],
    kernel_env: dict[str, str],
    enable_subagents: bool,
    subagent_mode: bool = False,
)
```

Everything the agent needs at runtime, resolved from config + environment.

Produced by resolve(). Unlike FreeactConfig, values here are concrete: `${VAR}` references substituted, presets expanded into server configs, and the model ready for pydantic-ai.

### for_subagent

```
for_subagent() -> ResolvedRuntime
```

Derive the runtime for a subagent.

Subagents cannot nest, and in hybrid discovery mode they neither sync nor watch the shared search index.

## freeact.config.Workspace

```
Workspace(working_dir: Path)
```

Filesystem layout of a freeact workspace.

## freeact.config.SkillMetadata

Bases: `BaseModel`

Metadata parsed from a skill's SKILL.md frontmatter.

Config:

- `frozen`: `True`

Fields:

- `name` (`str`)
- `description` (`str`)
- `path` (`Path`)

## freeact.config.DEFAULT_MODEL_NAME

```
DEFAULT_MODEL_NAME = 'google-gla:gemini-3.6-flash'
```

## freeact.config.DEFAULT_MODEL_SETTINGS

```
DEFAULT_MODEL_SETTINGS: dict[str, Any] = {
    "google_thinking_config": {
        "thinking_level": "medium",
        "include_thoughts": True,
    }
}
```

## freeact.config.FILESYSTEM_MCP_SERVER_CONFIG

```
FILESYSTEM_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.filesystem"],
}
```

## freeact.config.BASIC_SEARCH_MCP_SERVER_CONFIG

```
BASIC_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.basic"],
    "env": {"PYTOOLS_DIR": "${PYTOOLS_DIR}"},
}
```

## freeact.config.HYBRID_SEARCH_MCP_SERVER_CONFIG

```
HYBRID_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.hybrid"],
    "env": {
        "GEMINI_API_KEY": "${GEMINI_API_KEY}",
        "PYTOOLS_DIR": "${PYTOOLS_DIR}",
        "PYTOOLS_DB_PATH": "${PYTOOLS_DB_PATH}",
        "PYTOOLS_EMBEDDING_MODEL": "${PYTOOLS_EMBEDDING_MODEL}",
        "PYTOOLS_EMBEDDING_DIM": "${PYTOOLS_EMBEDDING_DIM}",
        "PYTOOLS_SYNC": "${PYTOOLS_SYNC}",
        "PYTOOLS_WATCH": "${PYTOOLS_WATCH}",
        "PYTOOLS_BM25_WEIGHT": "${PYTOOLS_BM25_WEIGHT}",
        "PYTOOLS_VEC_WEIGHT": "${PYTOOLS_VEC_WEIGHT}",
    },
}
```

## freeact.config.GOOGLE_SEARCH_MCP_SERVER_CONFIG

```
GOOGLE_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": [
        "-m",
        "freeact.tools.gsearch",
        "--thinking-level",
        "medium",
    ],
    "env": {"GEMINI_API_KEY": "${GEMINI_API_KEY}"},
}
```

## freeact.config.FETCH_MCP_SERVER_CONFIG

```
FETCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.fetch"],
    "env": {},
}
```
