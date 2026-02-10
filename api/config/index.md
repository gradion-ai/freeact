## freeact.agent.config.Config

```
Config(
    working_dir: Path | None = None,
    model: str | Model = DEFAULT_MODEL,
    model_settings: ModelSettings = DEFAULT_MODEL_SETTINGS,
)
```

Configuration loader for the `.freeact/` directory structure.

Loads and parses all configuration on instantiation: skills metadata, system prompts, MCP servers (JSON tool calls), and PTC servers (programmatic tool calling).

Internal MCP servers (pytools, filesystem) are defined as constants in this module. User-defined servers from `config.json` override internal configs when they share the same key.

Attributes:

| Name              | Type  | Description                                                     |
| ----------------- | ----- | --------------------------------------------------------------- |
| `working_dir`     |       | Agent's working directory.                                      |
| `freeact_dir`     |       | Path to .freeact/ configuration directory.                      |
| `plans_dir`       |       | Path to .freeact/plans/ for plan storage.                       |
| `model`           |       | LLM model name or instance.                                     |
| `model_settings`  |       | Model-specific settings (e.g., thinking config).                |
| `tool_search`     | `str` | Tool discovery mode read from config.json.                      |
| `skills_metadata` |       | Parsed skill definitions from .freeact/skills/\*/SKILL.md.      |
| `system_prompt`   |       | Rendered system prompt loaded from package resources.           |
| `mcp_servers`     |       | Merged MCP server configs (internal defaults + user overrides). |
| `ptc_servers`     |       | Raw PTC server configs loaded from config.json.                 |

## freeact.agent.config.SkillMetadata

```
SkillMetadata(name: str, description: str, path: Path)
```

Metadata parsed from a skill's SKILL.md frontmatter.

## freeact.agent.config.init_config

```
init_config(working_dir: Path | None = None) -> None
```

Initialize `.freeact/` config directory from templates.

Copies template files that don't already exist, preserving user modifications.

Parameters:

| Name          | Type   | Description | Default                                                |
| ------------- | ------ | ----------- | ------------------------------------------------------ |
| `working_dir` | \`Path | None\`      | Base directory. Defaults to current working directory. |

## freeact.agent.config.DEFAULT_MODEL

```
DEFAULT_MODEL = 'gemini-3-flash-preview'
```

## freeact.agent.config.DEFAULT_MODEL_SETTINGS

```
DEFAULT_MODEL_SETTINGS = GoogleModelSettings(
    google_thinking_config={
        "thinking_level": "high",
        "include_thoughts": True,
    }
)
```

## freeact.agent.config.PYTOOLS_BASIC_CONFIG

```
PYTOOLS_BASIC_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": [
        "-m",
        "freeact.agent.tools.pytools.search.basic",
    ],
}
```

## freeact.agent.config.PYTOOLS_HYBRID_CONFIG

```
PYTOOLS_HYBRID_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": [
        "-m",
        "freeact.agent.tools.pytools.search.hybrid",
    ],
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

## freeact.agent.config.FILESYSTEM_CONFIG

```
FILESYSTEM_CONFIG: dict[str, Any] = {
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
