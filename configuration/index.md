# Configuration

Freeact configuration is stored in the `.freeact/` directory. This page describes the directory structure and configuration formats. It also describes the structure of [tool directories](#tool-directories).

## Initialization

The `.freeact/` directory is created and populated from bundled templates through three entry points:

| Entry Point                | Description                                                                                                  |
| -------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `freeact` or `freeact run` | Creates config with [CLI tool](https://gradion-ai.github.io/freeact/cli/index.md) before starting the agent  |
| `freeact init`             | Creates config with [CLI tool](https://gradion-ai.github.io/freeact/cli/index.md) without starting the agent |
| Config.init()              | Creates config programmatically without starting the agent                                                   |

All three entry points share the same behavior:

- **Missing files are created** from [default templates](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates)
- **Existing files are preserved** and never overwritten
- **User modifications persist** across restarts and updates

This allows safe customization: edit any configuration file, and your changes remain intact. If you delete a file, it is recreated from the default template on next initialization.

## Directory Structure

```
.freeact/
├── config.json         # Configuration and MCP server definitions
├── skills/             # Agent skills
│   └── <skill-name>/
│       ├── SKILL.md    # Skill metadata and instructions
│       └── ...         # Further skill resources
├── generated/          # Generated tool sources (on PYTHONPATH)
│   ├── mcptools/       # Generated Python APIs from ptc-servers
│   └── gentools/       # User-defined tools saved from code actions
├── plans/              # Task plan storage
├── sessions/           # Session trace storage
│   └── <session-uuid>/
│       ├── main.jsonl
│       └── sub-xxxx.jsonl
└── permissions.json    # Persisted approval decisions
```

## Configuration File

The `config.json` file contains agent settings and MCP server configurations:

```
{
  "model": "google-gla:gemini-3-flash-preview",
  "model-settings": { ... },
  "tool-search": "basic",
  "images-dir": null,
  "execution-timeout": 300,
  "approval-timeout": null,
  "enable-subagents": true,
  "max-subagents": 5,
  "kernel-env": {},
  "mcp-servers": {},
  "ptc-servers": {
    "server-name": { ... }
  }
}
```

### Agent Settings

| Setting             | Default                             | Description                                                                                                                                                     |
| ------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`             | `google-gla:gemini-3-flash-preview` | [Model identifier](https://gradion-ai.github.io/freeact/models/#model-identifier) in `provider:model-name` format                                               |
| `model-settings`    | `{}`                                | Provider-specific [model settings](https://gradion-ai.github.io/freeact/models/#model-settings) (e.g., thinking config, temperature)                            |
| `model-provider`    | `null`                              | Custom API credentials, endpoints, or other [provider-specific options](https://gradion-ai.github.io/freeact/models/#model-provider)                            |
| `images-dir`        | `null`                              | Directory for saving generated images to disk. `null` defaults to `images` in the working directory.                                                            |
| `execution-timeout` | `300`                               | Maximum time in seconds for [code execution](https://gradion-ai.github.io/freeact/execution/index.md). Approval wait time is excluded. `null` means no timeout. |
| `approval-timeout`  | `null`                              | Timeout in seconds for PTC approval requests. `null` means no timeout.                                                                                          |
| `enable-subagents`  | `true`                              | Whether to enable subagent delegation                                                                                                                           |
| `max-subagents`     | `5`                                 | Maximum number of concurrent subagents                                                                                                                          |
| `kernel-env`        | `{}`                                | Environment variables passed to the IPython kernel. Supports `${VAR}` placeholders resolved against the host environment.                                       |

### `tool-search`

Controls how the agent discovers Python tools:

| Mode     | Description                                                                 |
| -------- | --------------------------------------------------------------------------- |
| `basic`  | Category browsing with `pytools_list_categories` and `pytools_list_tools`   |
| `hybrid` | BM25/vector search with `pytools_search_tools` for natural language queries |

The `tool-search` setting also selects the matching system prompt template (see [System Prompt](#system-prompt)). For hybrid mode environment variables, see [Hybrid Search](#hybrid-search).

### `mcp-servers`

MCP servers called directly via JSON tool calls. Internal servers (`pytools` for basic or hybrid tool search and filesystem for file operations) are provided automatically and do not need to be configured. User-defined servers in this section are merged with the internal defaults. If a user entry uses the same key as an internal server, the user entry takes precedence.

Custom MCP servers

Application-specific MCP servers for JSON tool calls can be added to this section as needed.

### `ptc-servers`

MCP servers called programmatically via generated Python APIs. This is freeact's implementation of *code mode*[1](#fn:1), where the agent calls MCP tools by writing code against generated APIs rather than through JSON tool calls. This allows composing multiple tool calls, processing intermediate results, and using control flow within a single code action.

Python APIs must be generated from `ptc-servers` to `.freeact/generated/mcptools/<server-name>/<tool>.py` before the agent can use them. The [CLI tool](https://gradion-ai.github.io/freeact/cli/index.md) handles this automatically. When using the [Agent SDK](https://gradion-ai.github.io/freeact/sdk/index.md), call generate_mcp_sources() explicitly. Code actions can then import and call the generated APIs because `.freeact/generated/` is on the kernel's `PYTHONPATH`.

The default configuration includes the bundled `google` MCP server (web search via Gemini):

```
{
  "ptc-servers": {
    "google": {
      "command": "python",
      "args": ["-m", "freeact.tools.gsearch", "--thinking-level", "medium"],
      "env": {"GEMINI_API_KEY": "${GEMINI_API_KEY}"}
    }
  }
}
```

Custom MCP servers

Application-specific MCP servers can be added as needed to `ptc-servers` for programmatic tool calling.

### Server Formats

Both `mcp-servers` and `ptc-servers` support stdio servers and streamable HTTP servers.

### Environment Variables

Server configurations support environment variable references using `${VAR_NAME}` syntax. Config() validates that all referenced variables are set. If a variable is missing, loading fails with an error.

## Hybrid Search

When `tool-search` is set to `"hybrid"` in `config.json`, the hybrid search server reads additional configuration from environment variables. Default values are provided for all optional variables:

| Variable                  | Default                           | Description                                           |
| ------------------------- | --------------------------------- | ----------------------------------------------------- |
| `GEMINI_API_KEY`          | *(required)*                      | API key for the default embedding model               |
| `PYTOOLS_DIR`             | `.freeact/generated`              | Base directory containing `mcptools/` and `gentools/` |
| `PYTOOLS_DB_PATH`         | `.freeact/search.db`              | Path to SQLite database for search index              |
| `PYTOOLS_EMBEDDING_MODEL` | `google-gla:gemini-embedding-001` | Embedding model identifier                            |
| `PYTOOLS_EMBEDDING_DIM`   | `3072`                            | Embedding vector dimensions                           |
| `PYTOOLS_SYNC`            | `true`                            | Sync index with tool directories on startup           |
| `PYTOOLS_WATCH`           | `true`                            | Watch tool directories for changes                    |
| `PYTOOLS_BM25_WEIGHT`     | `1.0`                             | Weight for BM25 (keyword) results in hybrid fusion    |
| `PYTOOLS_VEC_WEIGHT`      | `1.0`                             | Weight for vector (semantic) results in hybrid fusion |

To use a different embedding provider, change `PYTOOLS_EMBEDDING_MODEL` to a supported [pydantic-ai embedder](https://ai.pydantic.dev/embeddings/) identifier.

Testing without an API key

Set `PYTOOLS_EMBEDDING_MODEL=test` to use a test embedder that generates deterministic embeddings. This is useful for development and testing but produces meaningless search results.

## System Prompt

The system prompt is an internal resource bundled with the package. The template used depends on the `tool-search` setting in `config.json`:

| Mode     | Template           | Description                                                               |
| -------- | ------------------ | ------------------------------------------------------------------------- |
| `basic`  | `system-basic.md`  | Category browsing with `pytools_list_categories` and `pytools_list_tools` |
| `hybrid` | `system-hybrid.md` | Semantic search with `pytools_search_tools`                               |

The template supports placeholders:

| Placeholder           | Description                                           |
| --------------------- | ----------------------------------------------------- |
| `{working_dir}`       | The agent's workspace directory                       |
| `{generated_rel_dir}` | Relative path to the generated tool sources directory |
| `{skills}`            | Rendered metadata from skills in `.freeact/skills/`   |

See the templates for [basic](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/prompts/system-basic.md) and [hybrid](https://github.com/gradion-ai/freeact/blob/main/freeact/agent/config/prompts/system-hybrid.md) modes.

## Skills

Skills are filesystem-based capability packages that specialize agent behavior. A skill is a directory containing a `SKILL.md` file with metadata in YAML frontmatter, and optionally further skill resources. Skills follow the [agentskills.io](https://agentskills.io/specification/) specification.

### Bundled Skills

Freeact contributes three skills to `.freeact/skills/`:

| Skill                                                                                                                    | Description                                                            |
| ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| [output-parsers](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/output-parsers)   | Generate output parsers for `mcptools/` with unstructured return types |
| [saving-codeacts](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/saving-codeacts) | Save generated code actions as reusable tools in `gentools/`           |
| [task-planning](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/task-planning)     | Basic task planning and tracking workflows                             |

Tool authoring

The `output-parsers` and `saving-codeacts` skills enable tool authoring. See [Enhancing Tools](https://gradion-ai.github.io/freeact/examples/output-parser/index.md) and [Code Action Reuse](https://gradion-ai.github.io/freeact/examples/saving-codeacts/index.md) for walkthroughs.

Custom agent skills

Custom skills can be added as needed to specialize agent behavior for specific applications.

## Permissions

[Tool permissions](https://gradion-ai.github.io/freeact/sdk/#permissions-api) are stored in `.freeact/permissions.json` based on tool name:

```
{
  "allowed_tools": [
    "tool_name_1",
    "tool_name_2"
  ]
}
```

Tools in `allowed_tools` are auto-approved by the [CLI tool](https://gradion-ai.github.io/freeact/cli/index.md) without prompting. Selecting `"a"` at the approval prompt adds the tool to this list.

## Tool Directories

The agent discovers tools from two directories under `.freeact/generated/`:

### `mcptools/`

Generated Python APIs from `ptc-servers` schemas:

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

______________________________________________________________________

1. [Code Mode: the better way to use MCP](https://blog.cloudflare.com/code-mode/) [↩](#fnref:1 "Jump back to footnote 1 in the text")
