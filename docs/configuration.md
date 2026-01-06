# Configuration

Freeact configuration is stored in the `.freeact/` directory. This page describes the directory structure and configuration formats. It also describes the structure of [tool directories](#tool-directories).

## Initialization

The `.freeact/` directory is created and populated from bundled templates through three entry points:

| Entry Point | Description |
|-------------|-------------|
| `freeact` or<br/> `freeact run` | Creates config with [CLI tool](cli.md) before starting the agent |
| `freeact init` | Creates config with [CLI tool](cli.md) without starting the agent |
| [`init_config()`][freeact.agent.config.init.init_config] | Creates config programmatically without starting the agent |

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
└── permissions.json     # Persisted approval decisions
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

These are MCP servers that are called directly via JSON. This section is primarily for freeact-internal servers. The default configuration includes the bundled `pytools` MCP server (for tool discovery) and the `filesystem` MCP server:

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

These are MCP servers called programmatically via Python APIs. Python APIs must be generated from `ptc-servers` to `mcptools/<server-name>/<tool>.py` before the agent can use them. The [CLI tool](cli.md) handles this automatically. When using the [Python SDK](sdk.md), call [`generate_mcp_sources()`][freeact.agent.tools.pytools.apigen.generate_mcp_sources] explicitly. Code actions can then import and call the generated APIs.

The default configuration includes the bundled `google` MCP server (web search via Gemini):

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

!!! tip "Custom MCP servers"
    Application-specific MCP servers can be added as needed to `ptc-servers` for programmatic tool calling.

### Environment Variables

Server configurations support environment variable references using `${VAR_NAME}` syntax. [`Config()`][freeact.agent.config.Config] validates that all referenced variables are set. If a variable is missing, loading fails with an error.

## System Prompt

The system prompt template is stored in `.freeact/prompts/system.md`. The template supports placeholders:

| Placeholder | Description |
|-------------|-------------|
| `{working_dir}` | The agent's workspace directory |
| `{skills}` | Rendered metadata from skills in `.freeact/skills/` |

See the [default template](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/templates/prompts/system.md) for details.

!!! tip "Custom system prompt"
    The system prompt can be extended or modified to specialize agent behavior for specific applications.

## Skills

Skills are filesystem-based capability packages that specialize agent behavior. A skill is a directory containing a `SKILL.md` file with metadata in YAML frontmatter, and optionally further skill resources. Skills follow the [agentskills.io](https://agentskills.io/specification/) specification.

### Bundled Skills

Freeact contributes three skills to `.freeact/skills/`:

| Skill | Description |
|-------|-------------|
| [output-parsers](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/output-parsers) | Generate output parsers for `mcptools/` with unstructured return types |
| [saving-codeacts](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/saving-codeacts) | Save generated code actions as reusable tools in `gentools/` |
| [task-planning](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/task-planning) | Basic task planning and tracking workflows |

!!! tip "Custom agent skills"
    Custom skills can be added as needed to specialize agent behavior for specific applications.

## Permissions

[Tool permissions](sdk.md#permissions-api) are stored in `.freeact/permissions.json` based on tool name:

```json
{
  "allowed_tools": [
    "tool_name_1",
    "tool_name_2"
  ]
}
```

Tools in `allowed_tools` are auto-approved by the [CLI tool](cli.md) without prompting. Selecting `"a"` at the approval prompt adds the tool to this list.

## Tool Directories

The agent discovers tools from two directories:

### `mcptools/`

Generated Python APIs from `ptc-servers` schemas:

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
