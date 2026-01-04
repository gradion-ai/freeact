# Configuration

Freeact configuration is stored in the `.freeact/` directory. This page describes the directory structure and configuration formats.

## Initialization

The `.freeact/` directory is created and populated from bundled templates through three entry points:

| Entry Point | Description |
|-------------|-------------|
| `freeact` or `freeact run` | [Terminal interface](cli.md) - initializes config before starting |
| `freeact init` | Explicit initialization - creates config without starting the agent |
| [`init_config()`][freeact.agent.config.init.init_config] | [Python SDK](python-sdk.md) - call directly for programmatic control |

All three entry points share the same behavior:

- **Missing files are created** from [default templates](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates)
- **Existing files are preserved** and never overwritten
- **User modifications persist** across restarts and updates

This allows safe customization: edit any configuration file, and your changes remain intact. If you delete a file, it is recreated from the default template on next initialization.

## Directory Structure

```
.freeact/
├── prompts/
│   └── system.md        # System prompt template
├── servers.json         # MCP server configurations
├── skills/              # Agent skills
│   └── <skill-name>/
│       ├── SKILL.md     # Skill metadata and instructions
│       └── ...          # Further skill resources
├── plans/               # Task plan storage
└── permissions.json     # Persisted tool permissions
```

## MCP Server Configuration

The `servers.json` file configures two types of MCP servers:

```json
{
  "mcp-servers": {
    "server-name": { ... }
  },
  "ptc-servers": {
    "server-name": { ... }
  }
}
```

Both sections support stdio servers and streamable HTTP servers.

### `mcp-servers`

These are MCP servers that are called directly via JSON. This section is primarily for freeact-internal servers. The default configuration includes `pytools` (tool discovery) and `filesystem` (file operations):

```json
{
  "mcp-servers": {
    "pytools": {
      "command": "python",
      "args": ["-m", "freeact.agent.tools.pytools.search"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    }
  }
}
```

### `ptc-servers`

These are MCP servers called programmatically via Python APIs auto-generated to `mcptools/<server-name>/<tool>.py`. Code actions import and call these APIs. The default configuration includes `google` (web search via Gemini):

```json
{
  "ptc-servers": {
    "google": {
      "command": "python",
      "args": ["-m", "freeact.agent.tools.gsearch", "--thinking-level", "medium"],
      "env": {"GEMINI_API_KEY": "${GEMINI_API_KEY}"}
    }
  }
}
```

Python APIs must be generated for `ptc-servers` before the agent can use them. The [CLI](cli.md) handles this automatically, generating APIs only for servers not yet present in `mcptools/`. When using the [Python SDK](python-sdk.md), you must call [`generate_mcp_sources()`][freeact.agent.tools.pytools.apigen.generate_mcp_sources] yourself. See [API generation](python-sdk.md#api-generation) for details.

!!! hint "Custom MCP servers"

    To add your own MCP servers, extend this section.

### Environment Variables

Use `${VAR_NAME}` syntax to reference environment variables. Missing variables raise an error when loading the configuration via [`Config()`][freeact.agent.config.Config].

## System Prompt

The system prompt template is stored in `.freeact/prompts/system.md`. It supports placeholders:

| Placeholder | Description |
|-------------|-------------|
| `{working_dir}` | The agent's workspace directory |
| `{skills}` | Rendered list of available skills with descriptions |

See the [default template](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/templates/prompts/system.md) for details.

## Skills

Skills are filesystem-based capability packages that extend agent behavior. Each skill is a directory containing a `SKILL.md` file with YAML frontmatter. Skills follow the [Agent Skills specification](https://agentskills.io/specification/).

### Built-in Skills

Freeact includes three default skills in `.freeact/skills/`:

| Skill | Description |
|-------|-------------|
| [output-parsers](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/templates/skills/output-parsers/SKILL.md) | Generate output parsers for `mcptools/` with unstructured return types |
| [saving-codeacts](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/templates/skills/saving-codeacts/SKILL.md) | Save generated code actions as reusable tools in `gentools/` |
| [task-planning](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/templates/skills/task-planning/SKILL.md) | Basic task planning and tracking workflows |

See [Agent Skills](features/agent-skills.md) for usage details.

## Permissions

Tool permissions are stored in `.freeact/permissions.json`. The current basic [`PermissionManager`][freeact.permissions.PermissionManager] implementation uses tool name based permissions:

```json
{
  "allowed_tools": [
    "tool_name_1",
    "tool_name_2"
  ]
}
```

Tools in the `allowed_tools` list execute without prompting for approval in the terminal interface. This file is updated when you grant an *always allow* (`a`) permission.

### Permission Tiers

1. **Always allowed** - Persisted in `permissions.json`, applies across sessions
2. **Session allowed** - In-memory only, cleared when the agent stops

## Tool Directories

The agent discovers tools from two directories:

### `mcptools/`

Auto-generated Python APIs from `ptc-servers` schemas:

```
mcptools/
└── <server-name>/
    └── <tool>.py        # Generated tool module
```

### `gentools/`

User-defined tools saved from successful code actions:

```
gentools/
└── <category>/
    └── <tool>/
        ├── __init__.py
        ├── api.py       # Public interface
        └── impl.py      # Implementation
```

See [Reusable Code Actions](features/reusable-codeacts.md) for creating tools from code actions.
