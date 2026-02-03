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

Attributes:

| Name              | Type | Description                                                |
| ----------------- | ---- | ---------------------------------------------------------- |
| `working_dir`     |      | Agent's working directory.                                 |
| `freeact_dir`     |      | Path to .freeact/ configuration directory.                 |
| `plans_dir`       |      | Path to .freeact/plans/ for plan storage.                  |
| `model`           |      | LLM model name or instance.                                |
| `model_settings`  |      | Model-specific settings (e.g., thinking config).           |
| `skills_metadata` |      | Parsed skill definitions from .freeact/skills/\*/SKILL.md. |
| `system_prompt`   |      | Rendered system prompt from .freeact/prompts/system.md.    |
| `mcp_servers`     |      | MCPServer instances used for JSON tool calling.            |
| `ptc_servers`     |      | Raw PTC server configs for programmatic tool generation.   |

## freeact.agent.config.SkillMetadata

```
SkillMetadata(name: str, description: str, path: Path)
```

Metadata parsed from a skill's SKILL.md frontmatter.

## freeact.agent.config.init_config

```
init_config(
    working_dir: Path | None = None,
    tool_search: Literal["basic", "hybrid"] = "basic",
) -> None
```

Initialize `.freeact/` config directory from templates.

Copies template files that don't already exist, preserving user modifications. Enforces the pytools server configuration based on the tool_search setting.

Parameters:

| Name          | Type                         | Description                                                                                                                                                             | Default                                                |
| ------------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `working_dir` | \`Path                       | None\`                                                                                                                                                                  | Base directory. Defaults to current working directory. |
| `tool_search` | `Literal['basic', 'hybrid']` | Tool discovery mode. "basic" uses category browsing via list_categories and list_tools. "hybrid" uses BM25/vector search via search_tools for natural language queries. | `'basic'`                                              |

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
