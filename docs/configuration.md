# Configuration

Freeact configuration is stored in the `.freeact/` directory. This page describes the directory structure and configuration formats. It also describes the structure of [tool directories](#tool-directories).

## Initialization

The `.freeact/` directory is initialized through CLI entry points:

| Entry Point | Description |
|-------------|-------------|
| `freeact` or<br/> `freeact run` | Initializes `.freeact/` on first run, then starts the agent. |
| `freeact init` | Initializes `.freeact/` without starting the agent. |

Both CLI entry points initialize only when `.freeact/` is missing. For programmatic agent configuration, see the [Agent SDK](sdk.md) and [Configuration API](api/config.md).

## Directory Structure

Freeact stores agent configuration and runtime state in `.freeact/`. Project-level customization uses `AGENTS.md` for [project instructions](#project-instructions) and `.agents/skills/` for [custom skills](#custom-skills).

```
<working-dir>/
├── AGENTS.md               # Project instructions (injected into system prompt)
├── .agents/
│   └── skills/             # Custom skills
│       └── <skill-name>/
│           ├── SKILL.md
│           └── ...
└── .freeact/
    ├── agent.json          # Configuration and MCP server definitions
    ├── terminal.json       # Terminal UI behavior and keybindings
    ├── skills/             # Bundled skills
    │   └── <skill-name>/
    │       ├── SKILL.md    # Skill metadata and instructions
    │       └── ...         # Further skill resources
    ├── generated/          # Generated tool sources (on PYTHONPATH)
    │   ├── mcptools/       # Generated Python APIs from ptc_servers
    │   └── gentools/       # User-defined tools saved from code actions
    ├── plans/              # Task plan storage
    ├── sessions/           # Session trace storage
    │   └── <session-uuid>/
    │       ├── main.jsonl
    │       ├── sub-xxxx.jsonl
    │       └── tool-results/
    │           └── <file-id>.<ext>   # Large tool results stored as files
    └── permissions.json    # Persisted approval decisions
```

## Configuration File

The `agent.json` file contains agent settings and MCP server configurations:

```json
{
  "model": "google-gla:gemini-3-flash-preview",
  "model_settings": { ... },
  "tool_search": "basic",
  "images_dir": null,
  "execution_timeout": 300,
  "approval_timeout": null,
  "tool_result_inline_max_bytes": 32768,
  "tool_result_preview_lines": 10,
  "enable_persistence": true,
  "enable_subagents": true,
  "max_subagents": 5,
  "kernel_env": {},
  "mcp_servers": {},
  "ptc_servers": {
    "server-name": { ... }
  }
}
```

### Agent Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `model` | `google-gla:gemini-3-flash-preview` | [Model identifier](models.md#model-identifier) in `provider:model-name` format |
| `model_settings` | `{}` | Provider-specific [model settings](models.md#model-settings) (e.g., thinking config, temperature) |
| `provider_settings` | `null` | Custom API credentials, endpoints, or other [provider-specific options](models.md#provider-settings) |
| `images_dir` | `null` | Directory for saving generated images to disk. `null` defaults to `images` in the working directory. |
| `execution_timeout` | `300` | Maximum time in seconds for [code execution](execution.md). Approval wait time is excluded. `null` means no timeout. |
| `approval_timeout` | `null` | Timeout in seconds for PTC approval requests. `null` means no timeout. |
| `tool_result_inline_max_bytes` | `32768` | Inline size threshold in bytes for tool results. Larger results are saved to `.freeact/sessions/<session-id>/tool-results/` and replaced with a file reference notice plus preview lines. |
| `tool_result_preview_lines` | `10` | Number of preview lines included from both the beginning and end of large text results in the file reference notice. |
| `enable_persistence` | `true` | Persist message history to `.freeact/sessions/` and allow session resume with `session_id`. If `false`, history stays in memory for the process lifetime only. |
| `enable_subagents` | `true` | Whether to enable subagent delegation |
| `max_subagents` | `5` | Maximum number of concurrent subagents |
| `kernel_env` | `{}` | Environment variables passed to the IPython kernel. Supports `${VAR}` placeholders resolved against the host environment. |

### `tool_search`

Controls how the agent discovers Python tools:

| Mode | Description |
|------|-------------|
| `basic` | Category browsing with `pytools_list_categories` and `pytools_list_tools` |
| `hybrid` | BM25/vector search with `pytools_search_tools` for natural language queries |

The `tool_search` setting also selects the matching system prompt template (see [System Prompt](#system-prompt)). For hybrid mode environment variables, see [Hybrid Search](#hybrid-search).

### `mcp_servers`

MCP servers called directly via JSON tool calls. Internal servers (`pytools` for [basic][freeact.agent.config.BASIC_SEARCH_MCP_SERVER_CONFIG] or [hybrid][freeact.agent.config.HYBRID_SEARCH_MCP_SERVER_CONFIG] tool search and [`filesystem`][freeact.agent.config.FILESYSTEM_MCP_SERVER_CONFIG] for file operations) are provided automatically and do not need to be configured. User-defined servers in this section are merged with the internal defaults. If a user entry uses the same key as an internal server, the user entry takes precedence.

!!! tip "Custom MCP servers"
    Application-specific MCP servers for JSON tool calls can be added to this section as needed.

### `ptc_servers`

MCP servers called programmatically via generated Python APIs. This is freeact's implementation of *code mode*[^1], where the agent calls MCP tools by writing code against generated APIs rather than through JSON tool calls. This allows composing multiple tool calls, processing intermediate results, and using control flow within a single code action.

Python APIs must be generated from `ptc_servers` to `.freeact/generated/mcptools/<server-name>/<tool>.py` before the agent can use them. The [CLI tool](cli.md) handles this automatically. When using the [Agent SDK](sdk.md), call [`generate_mcp_sources()`][freeact.tools.pytools.apigen.generate_mcp_sources] explicitly. Code actions can then import and call the generated APIs because `.freeact/generated/` is on the kernel's `PYTHONPATH`.

The default configuration includes the bundled `google` MCP server (web search via Gemini):

```json
{
  "ptc_servers": {
    "google": {
      "command": "python",
      "args": ["-m", "freeact.tools.gsearch", "--thinking-level", "medium"],
      "env": {"GEMINI_API_KEY": "${GEMINI_API_KEY}"}
    }
  }
}
```

!!! tip "Custom MCP servers"
    Application-specific MCP servers can be added as needed to `ptc_servers` for programmatic tool calling.

### Server Formats

Both `mcp_servers` and `ptc_servers` support stdio servers and streamable HTTP servers.

### Environment Variables

Server configurations support environment variable references using `${VAR_NAME}` syntax. [`Config()`][freeact.agent.config.Config] validates that all referenced variables are set. If a variable is missing, loading fails with an error.

## Hybrid Search

When `tool_search` is set to `"hybrid"` in `agent.json`, the hybrid search server reads additional configuration from environment variables. Default values are provided for all optional variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | API key for the default embedding model |
| `PYTOOLS_DIR` | `.freeact/generated` | Base directory containing `mcptools/` and `gentools/` |
| `PYTOOLS_DB_PATH` | `.freeact/search.db` | Path to SQLite database for search index |
| `PYTOOLS_EMBEDDING_MODEL` | `google-gla:gemini-embedding-001` | Embedding model identifier |
| `PYTOOLS_EMBEDDING_DIM` | `3072` | Embedding vector dimensions |
| `PYTOOLS_SYNC` | `true` | Sync index with tool directories on startup |
| `PYTOOLS_WATCH` | `true` | Watch tool directories for changes |
| `PYTOOLS_BM25_WEIGHT` | `1.0` | Weight for BM25 (keyword) results in hybrid fusion |
| `PYTOOLS_VEC_WEIGHT` | `1.0` | Weight for vector (semantic) results in hybrid fusion |

To use a different embedding provider, change `PYTOOLS_EMBEDDING_MODEL` to a supported [pydantic-ai embedder](https://ai.pydantic.dev/embeddings/){target="_blank"} identifier.

!!! tip "Testing without an API key"
    Set `PYTOOLS_EMBEDDING_MODEL=test` to use a test embedder that generates deterministic embeddings. This is useful for development and testing but produces meaningless search results.

## System Prompt

The system prompt is an internal resource bundled with the package. The template used depends on the `tool_search` setting in `agent.json`:

| Mode | Template | Description |
|------|----------|-------------|
| `basic` | [`system-basic.md`](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/prompts/system-basic.md) | Category browsing with `pytools_list_categories` and `pytools_list_tools` |
| `hybrid` | [`system-hybrid.md`](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/prompts/system-hybrid.md) | Semantic search with `pytools_search_tools` |

The template supports placeholders:

| Placeholder | Description |
|-------------|-------------|
| `{working_dir}` | The agent's workspace directory |
| `{generated_rel_dir}` | Relative path to the generated tool sources directory |
| `{project_instructions}` | Content from `AGENTS.md`, wrapped in `<project-instructions>` tags. Omitted if the file is absent or empty. |
| `{skills}` | Rendered metadata from bundled skills (`.freeact/skills/`) and custom skills (`.agents/skills/`). Omitted if no skills exist. |

## Project Instructions

The agent loads project-specific instructions from an `AGENTS.md` file in the working directory. If the file exists and is non-empty, its content is injected into the system prompt. If the file is absent or empty, the section is omitted.

`AGENTS.md` provides project context to the agent: domain-specific conventions, workflow preferences, or any instructions relevant to the agent's tasks.

## Skills

Skills are filesystem-based capability packages that specialize agent behavior. A skill is a directory containing a `SKILL.md` file with metadata in YAML frontmatter, and optionally further skill resources. Skills follow the [agentskills.io](https://agentskills.io/specification/) specification. Skills are loaded on demand: only metadata is in context initially, full instructions load when relevant.

### Bundled Skills

Freeact contributes three bundled skills to `.freeact/skills/`:

| Skill | Description |
|-------|-------------|
| [output-parsers](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/output-parsers) | Generate output parsers for `mcptools/` with unstructured return types |
| [saving-codeacts](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/saving-codeacts) | Save generated code actions as reusable tools in `gentools/` |
| [task-planning](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/task-planning) | Basic task planning and tracking workflows |

Bundled skills are auto-created from templates on [initialization](#initialization). User modifications persist across restarts.

!!! hint "Tool authoring"
    The `output-parsers` and `saving-codeacts` skills enable tool authoring. See [Enhancing Tools](examples/output-parser.md) and [Code Action Reuse](examples/saving-codeacts.md) for walkthroughs.

### Custom Skills

Custom skills are loaded from `.agents/skills/` in the working directory. Each subdirectory containing a `SKILL.md` file is registered as a skill. Metadata of custom skills appears in the system prompt after bundled skills.

The `.agents/skills/` directory is not managed by freeact and is not auto-created.

!!! tip "Example"
    See [Custom Agent Skills](examples/agent-skills.md) for a walkthrough of installing and using a custom skill.

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

The agent discovers tools from two directories under `.freeact/generated/`:

### `mcptools/`

Generated Python APIs from `ptc_servers` schemas:

```
.freeact/generated/mcptools/
└── <server-name>/
    └── <tool>.py        # Generated tool module
```

### `gentools/`

User-defined tools saved from successful code actions:

```
.freeact/generated/gentools/
└── <category>/
    └── <tool>/
        ├── __init__.py
        ├── api.py       # Public interface
        └── impl.py      # Implementation
```

## Terminal UI

The `terminal.json` file configures terminal UI collapse behavior and keybindings.

```json
{
  "collapse_thoughts_on_complete": true,
  "collapse_exec_output_on_complete": true,
  "collapse_approved_code_actions": true,
  "collapse_approved_tool_calls": true,
  "collapse_tool_outputs": true,
  "keep_rejected_actions_expanded": true,
  "pin_pending_approval_action_expanded": true,
  "expand_all_toggle_key": "ctrl+o"
}
```

### Initialization

The CLI creates `terminal.json` during `freeact`, `freeact run`, and `freeact init` when the file is missing.

SDK integrations can load or initialize this file by calling `await freeact.terminal.config.Config.init()`.

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `collapse_thoughts_on_complete` | `true` | Collapse `Thinking` boxes after a completed `Thoughts` event. |
| `collapse_exec_output_on_complete` | `true` | Collapse `Execution Output` boxes after a completed `CodeExecutionOutput` event. |
| `collapse_approved_code_actions` | `true` | Collapse approved code action previews after approval. |
| `collapse_approved_tool_calls` | `true` | Collapse approved tool call previews after approval. |
| `collapse_tool_outputs` | `true` | Render `Tool Output` boxes collapsed by default. |
| `keep_rejected_actions_expanded` | `true` | Keep rejected action previews expanded after rejection. |
| `pin_pending_approval_action_expanded` | `true` | Keep the current pending approval action expanded until a decision is made. |
| `expand_all_toggle_key` | `ctrl+o` | Toggle all collapsible boxes between expanded and configured state. |

[^1]: [Code Mode: the better way to use MCP](https://blog.cloudflare.com/code-mode/)
