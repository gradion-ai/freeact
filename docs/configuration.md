# Configuration

Freeact configuration is stored in the `.freeact/` directory. This guide documents the directory structure and configuration formats.

## Directory Structure

```
.freeact/
├── prompts/
│   └── system.md        # System prompt template
├── servers.json         # MCP server configurations
├── skills/              # Agent skills
│   └── <skill-name>/
│       └── SKILL.md     # Skill definition
├── plans/               # Task plan storage
└── permissions.json     # Persisted tool permissions
```

## Server Configuration

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

### MCP Servers

MCP servers are called directly via JSON tool calls. Configure either stdio or HTTP servers:

**Stdio server:**

```json
{
  "mcp-servers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    }
  }
}
```

**HTTP server:**

```json
{
  "mcp-servers": {
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"}
    }
  }
}
```

### PTC Servers

PTC (Programmatic Tool Calling) servers have Python APIs auto-generated to `mcptools/<server-name>/`. The agent writes code that imports and calls these typed APIs.

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

### Environment Variables

Use `${VAR_NAME}` syntax to reference environment variables. Missing variables raise an error at startup.

## System Prompt

The system prompt template is stored in `.freeact/prompts/system.md`. It supports placeholders:

| Placeholder | Description |
|-------------|-------------|
| `{working_dir}` | Agent's current working directory |
| `{skills}` | Rendered list of available skills with descriptions |

Example template:

```markdown
You are a Python code execution agent.

## Working Directory

The current working directory is `{working_dir}`.

## Skills

{skills}
```

## Skills

Skills are filesystem-based capability packages that extend agent behavior. Each skill is a directory containing a `SKILL.md` file with YAML frontmatter.

### Skill Structure

```
.freeact/skills/<skill-name>/
├── SKILL.md            # Required: skill definition
└── <resources>         # Optional: additional files
```

### SKILL.md Format

```markdown
---
name: skill-name
description: Brief description of what the skill does. This appears in the skills list.
---

# Skill Title

Full instructions for the agent when this skill is activated.

## Workflow

1. Step one
2. Step two
...
```

The frontmatter fields:

| Field | Description |
|-------|-------------|
| `name` | Skill identifier (matches directory name) |
| `description` | Brief description shown in the skills listing |

The content after the frontmatter contains full instructions that load when the skill is triggered.

### Built-in Skills

Freeact includes three default skills:

- **output-parsers** - Generate output parsers for mcptools with unstructured return types
- **saving-codeacts** - Save executed Python code as reusable tools in gentools
- **task-planning** - Task planning and breakdown workflows

## Permissions

Tool permissions are stored in `.freeact/permissions.json`:

```json
{
  "allowed_tools": [
    "tool_name_1",
    "tool_name_2"
  ]
}
```

Tools in the `allowed_tools` list execute without prompting for approval. This file is updated when you grant "always allow" permission during interactive use.

### Permission Tiers

1. **Always allowed** - Persisted in `permissions.json`, applies across sessions
2. **Session allowed** - In-memory only, cleared when the agent stops
3. **Auto-approved** - Filesystem operations within `.freeact/` are always allowed

See [Approval Mechanism](features/approval.md) for details on the approval flow.

## Tool Directories

The agent discovers tools from two directories:

### mcptools/

Auto-generated Python APIs from PTC server schemas:

```
mcptools/
└── <server-name>/
    └── <tool>.py        # Generated tool module
```

### gentools/

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
