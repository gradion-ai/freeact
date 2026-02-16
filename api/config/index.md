## freeact.agent.config.Config

```
Config(working_dir: Path | None = None)
```

Configuration loader for the `.freeact/` directory structure.

Loads and parses all configuration on instantiation: skills metadata, system prompts, MCP servers (JSON tool calls), and PTC servers (programmatic tool calling).

Internal MCP servers (pytools, filesystem) are defined as constants in this module. User-defined servers from `config.json` override internal configs when they share the same key.

Attributes:

| Name                | Type             | Description                                                |
| ------------------- | ---------------- | ---------------------------------------------------------- |
| `working_dir`       | `Path`           | Agent's working directory.                                 |
| `freeact_dir`       | `Path`           | Path to .freeact/ configuration directory.                 |
| `model`             | `Path`           | LLM model name or instance.                                |
| `model_settings`    | `Path`           | Model-specific settings (e.g., thinking config).           |
| `tool_search`       | `str`            | Tool discovery mode read from config.json.                 |
| `images_dir`        | \`Path           | None\`                                                     |
| `execution_timeout` | \`float          | None\`                                                     |
| `approval_timeout`  | \`float          | None\`                                                     |
| `enable_subagents`  | `bool`           | Whether to enable subagent delegation.                     |
| `max_subagents`     | `int`            | Maximum number of concurrent subagents.                    |
| `kernel_env`        | `dict[str, str]` | Environment variables passed to the IPython kernel.        |
| `skills_metadata`   |                  | Parsed skill definitions from .freeact/skills/\*/SKILL.md. |
| `system_prompt`     |                  | Rendered system prompt loaded from package resources.      |
| `mcp_servers`       |                  | Merged and resolved MCP server configs.                    |
| `ptc_servers`       |                  | Raw PTC server configs loaded from config.json.            |
| `sessions_dir`      | `Path`           | Session trace storage directory.                           |

### freeact_dir

```
freeact_dir: Path
```

Path to `.freeact/` configuration directory.

### generated_dir

```
generated_dir: Path
```

Generated MCP tool sources directory.

### plans_dir

```
plans_dir: Path
```

Plan storage directory.

### search_db_file

```
search_db_file: Path
```

Hybrid search database path.

### sessions_dir

```
sessions_dir: Path
```

Session trace storage directory.

### working_dir

```
working_dir: Path
```

Agent's working directory.

### for_subagent

```
for_subagent() -> Config
```

Create a subagent configuration from this config.

Returns a shallow copy with subagent-specific overrides: subagents disabled, mcp_servers deep-copied with pytools sync/watch disabled, and kernel_env shallow-copied for independence.

### init

```
init(working_dir: Path | None = None) -> None
```

Scaffold `.freeact/` directory from bundled templates.

Copies template files that don't already exist, preserving user modifications. Runs blocking I/O in a separate thread.

Parameters:

| Name          | Type   | Description | Default                                                |
| ------------- | ------ | ----------- | ------------------------------------------------------ |
| `working_dir` | \`Path | None\`      | Base directory. Defaults to current working directory. |

## freeact.agent.config.SkillMetadata

```
SkillMetadata(name: str, description: str, path: Path)
```

Metadata parsed from a skill's SKILL.md frontmatter.

## freeact.agent.config.PYTOOLS_BASIC_CONFIG

```
PYTOOLS_BASIC_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.search.basic"],
    "env": {"PYTOOLS_DIR": "${PYTOOLS_DIR}"},
}
```

## freeact.agent.config.PYTOOLS_HYBRID_CONFIG

```
PYTOOLS_HYBRID_CONFIG: dict[str, Any] = {
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
