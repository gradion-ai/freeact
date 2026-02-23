## freeact.agent.config.Config

Bases: `BaseModel`

Agent configuration.

Config:

- `arbitrary_types_allowed`: `True`
- `extra`: `forbid`
- `validate_assignment`: `True`
- `frozen`: `True`

Fields:

- `working_dir` (`Path`)
- `model` (`str | Model`)
- `model_settings` (`dict[str, Any]`)
- `provider_settings` (`dict[str, Any] | None`)
- `tool_search` (`Literal['basic', 'hybrid']`)
- `images_dir` (`Path | None`)
- `execution_timeout` (`float | None`)
- `approval_timeout` (`float | None`)
- `tool_result_inline_max_bytes` (`int`)
- `tool_result_preview_lines` (`int`)
- `enable_persistence` (`bool`)
- `enable_subagents` (`bool`)
- `max_subagents` (`int`)
- `kernel_env` (`dict[str, str]`)
- `mcp_servers` (`dict[str, dict[str, Any]]`)
- `ptc_servers` (`dict[str, dict[str, Any]]`)

### init

```
init(working_dir: Path | None = None) -> Config
```

Load config from `.freeact/` when present, otherwise save defaults.

### load

```
load(working_dir: Path | None = None) -> Config
```

Load persisted config if present, otherwise return defaults.

### save

```
save() -> None
```

Persist config and scaffold static directories and bundled skills.

## freeact.agent.config.SkillMetadata

Bases: `BaseModel`

Metadata parsed from a skill's SKILL.md frontmatter.

Config:

- `frozen`: `True`

Fields:

- `name` (`str`)
- `description` (`str`)
- `path` (`Path`)

## freeact.agent.config.DEFAULT_MODEL_NAME

```
DEFAULT_MODEL_NAME = 'google-gla:gemini-3-flash-preview'
```

## freeact.agent.config.DEFAULT_MODEL_SETTINGS

```
DEFAULT_MODEL_SETTINGS: dict[str, Any] = {
    "google_thinking_config": {
        "thinking_level": "high",
        "include_thoughts": True,
    }
}
```

## freeact.agent.config.BASIC_SEARCH_MCP_SERVER_CONFIG

```
BASIC_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.search.basic"],
    "env": {"PYTOOLS_DIR": "${PYTOOLS_DIR}"},
}
```

## freeact.agent.config.HYBRID_SEARCH_MCP_SERVER_CONFIG

```
HYBRID_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.search.hybrid"],
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

## freeact.agent.config.GOOGLE_SEARCH_MCP_SERVER_CONFIG

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

## freeact.agent.config.FILESYSTEM_MCP_SERVER_CONFIG

```
FILESYSTEM_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "npx",
    "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        ".",
    ],
    "excluded_tools": [
        "create_directory",
        "list_directory",
        "list_directory_with_sizes",
        "directory_tree",
        "move_file",
        "search_files",
        "list_allowed_directories",
        "read_file",
    ],
}
```
