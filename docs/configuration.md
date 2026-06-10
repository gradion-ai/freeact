# Configuration

Freeact reads configuration from a single file, `.freeact/config.toml`, with an [`[agent]`](#agent-settings) and a [`[terminal]`](#terminal-ui) section. The file is human-owned: `freeact init` writes it once with commented defaults, and freeact never rewrites it afterwards. Approval decisions are stored separately in the machine-managed [`.freeact/permissions.toml`](#permissions).

## Initialization

The `.freeact/` directory is initialized through CLI entry points:

| Entry Point | Description |
|-------------|-------------|
| `freeact` or<br/> `freeact run` | Initializes `.freeact/` (missing pieces only), then starts the agent. |
| `freeact init` | Initializes `.freeact/` without starting the agent. |

Initialization writes `config.toml` when missing (never overwrites), creates the runtime directories (`generated/`, `plans/`, `sessions/`), materializes [bundled skills](#bundled-skills) without overwriting user-modified ones, and seeds `permissions.toml` with the [default rules](#default-rules). For programmatic configuration, see the [Agent SDK](sdk.md) and [Configuration API](api/config.md).

!!! warning "Migration from pre-rewrite versions"

    Earlier freeact versions stored configuration in `.freeact/agent.json`, `.freeact/terminal.json`, and `.freeact/permissions.json`. These files are now ignored; there is no automatic migration. Run `freeact init` to create `config.toml` and transfer your settings manually. Saved permission rules are not migrated: freeact prompts for approval again, and rules can be re-saved from the [approval prompt](cli.md#approval-prompt).

## Directory Structure

Freeact stores configuration and runtime state in `.freeact/`. Project-level customization uses `AGENTS.md` for [project instructions](#project-instructions) and `.agents/skills/` for [custom skills](#custom-skills).

```
<working-dir>/
├── AGENTS.md               # Project instructions (injected into system prompt)
├── .agents/
│   └── skills/             # Custom skills
│       └── <skill-name>/
│           ├── SKILL.md
│           └── ...
└── .freeact/
    ├── config.toml         # Agent and terminal configuration (human-owned)
    ├── permissions.toml    # Persisted approval decisions (machine-managed)
    ├── skills/             # Bundled skills
    │   └── <skill-name>/
    │       ├── SKILL.md    # Skill metadata and instructions
    │       └── ...         # Further skill resources
    ├── generated/          # Generated tool sources (on PYTHONPATH)
    │   ├── mcptools/       # Generated Python APIs from ptc_servers
    │   └── gentools/       # User-defined tools saved from code actions
    ├── plans/              # Task plan storage
    ├── sessions/           # Session trace storage
    │   └── <session-id>/
    │       ├── main.jsonl
    │       ├── sub-xxxx.jsonl
    │       └── tool-results/
    │           └── <file-id>.<ext>   # Large tool results stored as files
    └── search.db           # Hybrid discovery index (discovery = "hybrid")
```

## Configuration File

`freeact init` writes `config.toml` with commented defaults:

```toml title=".freeact/config.toml"
[agent]
model = "google-gla:gemini-3.5-flash"
# execution_timeout = 300.0     # seconds; 0 disables the timeout
# approval_timeout = 0.0        # seconds; 0 waits forever
# enable_persistence = true
# enable_subagents = true
# max_subagents = 5
# images_dir = "images"
# tool_result_inline_max_bytes = 32768
# tool_result_preview_chars = 2048

[agent.model_settings]
google_thinking_config = { thinking_level = "medium", include_thoughts = true }

# Provider options (api_key, base_url, ...). `${VAR}` reads environment variables.
# [agent.provider_settings]
# api_key = "${MY_PROVIDER_KEY}"

[agent.tools]
# One-line opt-ins for bundled tool servers. Code execution and filesystem
# tools are always available.
# search = true            # google search (code mode); needs GEMINI_API_KEY
# fetch = true             # web fetch (code mode)
# discovery = "basic"      # or "hybrid" (needs freeact[search]); omit for none

# Environment variables for the IPython kernel. `${VAR}` reads host env vars.
# [agent.kernel_env]
# MY_VAR = "${MY_VAR}"

# Custom MCP servers for JSON tool calling:
# [agent.mcp_servers.github]
# command = "docker"
# args = ["run", "-i", "--rm", "-e", "GITHUB_TOKEN", "ghcr.io/github/github-mcp-server"]
# env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
# exclude_tools = []

# Custom MCP servers for programmatic tool calling (generated Python APIs):
# [agent.ptc_servers.github]
# command = "..."
# args = []

[terminal]
# collapse_thoughts_on_complete = true
# collapse_exec_output_on_complete = true
# collapse_approved_code_actions = false
# collapse_approved_tool_calls = true
# collapse_completed_subagent_tasks = true
# collapse_tool_outputs = true
# keep_rejected_actions_expanded = true
# pin_pending_approval_action_expanded = true
# expand_all_toggle_key = "ctrl+o"
```

### Agent Settings

The `[agent]` section accepts these keys:

| Setting | Default | Description |
|---------|---------|-------------|
| `model` | `google-gla:gemini-3.5-flash` | [Model identifier](models.md#model-identifier) in `provider:model-name` format |
| `model_settings` | [Google thinking config](models.md#google-default) | Provider-specific [model settings](models.md#model-settings) (e.g., thinking config, temperature) |
| `provider_settings` | unset | Custom API credentials, endpoints, or other [provider-specific options](models.md#provider-settings) |
| `tools` | all off | [Tool presets](#tool-presets) for bundled tool servers |
| `execution_timeout` | `300` | Maximum time in seconds for each [code execution](execution.md). Approval wait time is excluded. `0` disables the timeout. |
| `approval_timeout` | `0` | Timeout in seconds for [approval requests](sdk.md#approval). An unresolved request is rejected when the timeout expires. `0` waits forever. |
| `tool_result_inline_max_bytes` | `32768` | Inline size threshold in bytes for tool results. Larger results are saved to `.freeact/sessions/<session-id>/tool-results/` and replaced with a file reference notice plus preview characters. |
| `tool_result_preview_chars` | `2048` | Number of preview characters included from both the beginning and end of large text results in the file reference notice. |
| `enable_persistence` | `true` | Persist message history to `.freeact/sessions/` and allow session resume with `session_id`. If `false`, history stays in memory for the process lifetime only. |
| `enable_subagents` | `true` | Whether to enable subagent delegation |
| `max_subagents` | `5` | Maximum number of concurrent subagents |
| `images_dir` | unset | Directory for saving generated images to disk. Unset defaults to `images` in the working directory; relative paths resolve against the working directory. |
| `kernel_env` | `{}` | Environment variables passed to the IPython kernel. Supports `${VAR}` placeholders resolved against the host environment. |
| `mcp_servers` | `{}` | [User-defined MCP servers](#mcp_servers) for JSON tool calling |
| `ptc_servers` | `{}` | [User-defined MCP servers](#ptc_servers) for programmatic tool calling |

### Tool Presets

The `[agent.tools]` section enables bundled tool servers with one line each. Defaults are minimal: everything is off, except code execution and filesystem tools, which are always available.

```toml
[agent.tools]
search = true            # google search (code mode); needs GEMINI_API_KEY
fetch = true             # web fetch (code mode)
discovery = "basic"      # or "hybrid" (needs freeact[search]); omit for none
```

| Preset | Default | Description |
|--------|---------|-------------|
| `search` | `false` | Adds the bundled `google` server (web search via Gemini with Google Search grounding) to [`ptc_servers`](#ptc_servers). Requires `GEMINI_API_KEY`. |
| `fetch` | `false` | Adds the bundled `fetch` server (URL content retrieval via [trafilatura](https://trafilatura.readthedocs.io/){target="_blank"}) to [`ptc_servers`](#ptc_servers). |
| `discovery` | unset | Tool discovery mode: `"basic"` or `"hybrid"`. Unset disables tool discovery. |

#### `discovery`

Controls how the agent discovers Python tools in [tool directories](#tool-directories):

| Mode | Description |
|------|-------------|
| `"basic"` | Category browsing with `pytools_list_categories` and `pytools_list_tools` |
| `"hybrid"` | BM25/vector search with `pytools_search_tools` for natural language queries |

Hybrid mode requires the `freeact[search]` [extra](installation.md#hybrid-tool-discovery) and `GEMINI_API_KEY` for the default embedding model. [Resolving](api/config.md) a config with `discovery = "hybrid"` fails with an install hint when the extra is missing. For hybrid mode environment variables, see [Hybrid Search](#hybrid-search).

### `mcp_servers`

MCP servers called directly via JSON tool calls, defined as `[agent.mcp_servers.<name>]` tables. Internal servers ([`filesystem`][freeact.config.FILESYSTEM_MCP_SERVER_CONFIG] for file operations and `pytools` for [basic][freeact.config.BASIC_SEARCH_MCP_SERVER_CONFIG] or [hybrid][freeact.config.HYBRID_SEARCH_MCP_SERVER_CONFIG] tool discovery) are provided automatically and do not need to be configured. User-defined servers are merged with the internal defaults. If a user entry uses the same key as an internal server, the user entry takes precedence.

```toml
[agent.mcp_servers.github]
command = "docker"
args = ["run", "-i", "--rm", "-e", "GITHUB_TOKEN", "ghcr.io/github/github-mcp-server"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
exclude_tools = []
```

The optional `exclude_tools` list hides individual server tools from the agent.

### `ptc_servers`

MCP servers called programmatically via generated Python APIs, defined as `[agent.ptc_servers.<name>]` tables. This is freeact's implementation of *code mode*[^1], where the agent calls MCP tools by writing code against generated APIs rather than through JSON tool calls. This allows composing multiple tool calls, processing intermediate results, and using control flow within a single code action.

Python APIs must be generated from `ptc_servers` to `.freeact/generated/mcptools/<server-name>/<tool>.py` before the agent can use them. The [CLI tool](cli.md) handles this automatically. When using the [Agent SDK](sdk.md), call [`generate_mcp_sources()`][freeact.tools.pytools.apigen.generate_mcp_sources] explicitly. Code actions can then import and call the generated APIs because `.freeact/generated/` is on the kernel's `PYTHONPATH`.

The [`search` and `fetch` presets](#tool-presets) add the bundled `google` and `fetch` servers to `ptc_servers`. Further bundled servers can be added manually:

```toml
[agent.ptc_servers.brave]
command = "python"
args = ["-m", "freeact.tools.bsearch"]
env = { BRAVE_API_KEY = "${BRAVE_API_KEY}" }
```

| Server | Module | Required env var | Description |
|--------|--------|-----------------|-------------|
| `google` | `freeact.tools.gsearch` | `GEMINI_API_KEY` | Web search via Gemini with Google Search grounding (enabled by the `search` preset) |
| `brave` | `freeact.tools.bsearch` | `BRAVE_API_KEY` | Web search via [Brave Search API](https://brave.com/search/api/){target="_blank"} with "web" and "llm-context" modes |
| `fetch` | `freeact.tools.fetch` | -- | Fetch and extract readable content from URLs via [trafilatura](https://trafilatura.readthedocs.io/){target="_blank"} (enabled by the `fetch` preset) |

!!! tip "Custom MCP servers"
    Application-specific MCP servers can be added as needed to `ptc_servers` for programmatic tool calling.

### Server Formats

Both `mcp_servers` and `ptc_servers` support stdio servers (`command`, `args`, `env`) and streamable HTTP servers (`url`, `headers`):

```toml
[agent.ptc_servers.github]
url = "https://api.githubcopilot.com/mcp/"
headers = { Authorization = "Bearer ${GITHUB_API_KEY}" }
```

### Environment Variables

`provider_settings`, `kernel_env`, and server configurations support environment variable references using `${VAR_NAME}` syntax. [`resolve()`][freeact.config.resolve] validates that all referenced variables are set; a missing variable fails resolution with an error naming the variable. The CLI loads a `.env` file from the working directory before resolution.

## Hybrid Search

When `discovery = "hybrid"` is set under `[agent.tools]`, the hybrid search server reads additional configuration from environment variables. Default values are provided for all optional variables:

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

The system prompt is an internal resource bundled with the package ([`system.md`](https://github.com/gradion-ai/freeact/blob/main/freeact/config/prompts/system.md)).

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
| [output-parsers](https://github.com/gradion-ai/freeact/tree/main/freeact/config/templates/skills/output-parsers) | Generate output parsers for `mcptools/` with unstructured return types |
| [saving-codeacts](https://github.com/gradion-ai/freeact/tree/main/freeact/config/templates/skills/saving-codeacts) | Save generated code actions as reusable tools in `gentools/` |
| [task-planning](https://github.com/gradion-ai/freeact/tree/main/freeact/config/templates/skills/task-planning) | Basic task planning and tracking workflows |

Bundled skills are auto-created from templates on [initialization](#initialization). User modifications persist across restarts.

!!! hint "Tool authoring"
    The `output-parsers` and `saving-codeacts` skills enable tool authoring. See [Enhancing Tools](examples/output-parser.md) and [Code Action Reuse](examples/saving-codeacts.md) for walkthroughs.

### Custom Skills

Custom skills are loaded from `.agents/skills/` in the working directory. Each subdirectory containing a `SKILL.md` file is registered as a skill. Metadata of custom skills appears in the system prompt after bundled skills.

The `.agents/skills/` directory is not managed by freeact and is not auto-created.

!!! tip "Example"
    See [Custom Agent Skills](examples/agent-skills.md) for a walkthrough of installing and using a custom skill.

## Permissions

[Permissions](sdk.md#permissions-api) control which code actions, shell commands, and tool calls require approval or are auto-approved. They are stored in `.freeact/permissions.toml` as typed rules with glob-style patterns. The file is machine-managed: freeact seeds it with [default rules](#default-rules) and appends rules saved from the [approval prompt](cli.md#approval-prompt). It can also be edited by hand; comments do not survive the next machine write.

`tool_name` and `command` fields support `*` (any characters) and `?` (single character). Path fields (`path`) use path-aware matching where `*` matches within a single directory and `**` matches across directory boundaries.

!!! tip "Bypassing permissions"
    The CLI supports a [`--skip-permissions`](cli.md#options) flag to run tools without prompting for approval, effectively auto-approving all actions.

```toml title=".freeact/permissions.toml"
ask = [
    { tool_name = "bash", type = "ShellAction", command = "rm *" },
]
allow = [
    { tool_name = "github_*", type = "GenericCall" },
    { tool_name = "bash", type = "ShellAction", command = "git *" },
    { tool_name = "filesystem_*", path = ".freeact/**", type = "FileRead" },
    { tool_name = "filesystem_*", path = "src/**", type = "FileWrite" },
]
```

Each rule has a `type` field that determines which fields are matched:

| Type | Matched fields |
|------|---------------|
| `GenericCall` | `tool_name` |
| `ShellAction` | `tool_name`, `command` |
| `CodeAction` | `tool_name` |
| `FileRead` | `tool_name`, `path` |
| `FileWrite` | `tool_name`, `path` |
| `FileEdit` | `tool_name`, `path` |

### Tiers

Permissions are organized into two tiers:

| Tier | Description |
|------|-------------|
| `allow` | Tool call executes without prompting |
| `ask` | User is always prompted for approval |

Evaluation order is **ask then allow**: if a rule matches both tiers, the user is prompted. Each tier supports two persistence scopes: **always** (persisted to `permissions.toml`) and **session** (in-memory, cleared when the session ends).

### Tool call patterns

Tool call patterns match against MCP tool names (e.g. `github_search_repositories`, `filesystem_read_text_file`). Filesystem tools (`FileRead`, `FileWrite`, `FileEdit`) additionally match on path fields, enabling path-specific rules like allowing reads only from `src/**`.

### Shell command patterns

`ShellAction` rules match on `tool_name` (`bash` for `!` commands, `shell_magic` for `%%bash` scripts) and `command`. The `command` field supports glob matching with `*` and `?`. Shell commands are intercepted during code execution with Python variables fully resolved, so patterns match against the actual command values.

| Pattern | Matches |
|---------|---------|
| `git *` | Any `git` command |
| `git commit *` | `git commit` with any arguments |
| `pip install *` | `pip install` with any package |
| `rm *` | Any `rm` command (use in `ask` tier to always prompt) |

When saving a permission rule via the [approval prompt](cli.md#approval-prompt), the CLI pre-fills a suggested pattern. The heuristic uses `cmd subcmd *` for known multi-word tools (git, pip, docker, kubectl, npm, uv, cargo, etc.) and `cmd *` for others. The user can edit the pattern before saving.

Composite shell commands joined with `&&`, `||`, `|`, or `;` are decomposed into individual sub-commands, each checked independently. If any sub-command is denied, the entire command is blocked.

### Path wildcards

Path fields (`path`) in `FileRead`, `FileWrite`, and `FileEdit` rules use path-aware matching. Paths are normalized relative to the working directory before matching: absolute paths under the working directory become relative, paths outside stay absolute.

| Wildcard | Scope |
|----------|-------|
| `*` | Matches within a single directory |
| `**` | Matches across directory boundaries |

The leading `/` determines whether a pattern targets paths inside or outside the working directory:

| Pattern | Inside working dir | Outside working dir |
|---------|--------------------|---------------------|
| `**` | Yes | No |
| `/**` | No | Yes |
| `src/**` | Yes (under `src/`) | No |

`tool_name` and `command` fields use standard glob matching where `*` matches any characters and `?` matches a single character.

### Default rules

On first run, `permissions.toml` is seeded with a generous set of read-only allow rules (file reads inside the working directory, common shell inspection commands like `ls`, `cat`, `git status`, and read-only built-in tools) plus an ask rule that always prompts for `.env` reads. Inspect `.freeact/permissions.toml` after the first run for the full list, and edit it to tighten or extend the defaults.

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

The `[terminal]` section of `config.toml` configures terminal UI collapse behavior and keybindings:

```toml
[terminal]
collapse_thoughts_on_complete = true
collapse_exec_output_on_complete = true
collapse_approved_code_actions = false
collapse_approved_tool_calls = true
collapse_completed_subagent_tasks = true
collapse_tool_outputs = true
keep_rejected_actions_expanded = true
pin_pending_approval_action_expanded = true
expand_all_toggle_key = "ctrl+o"
```

| Setting | Default | Description |
|---------|---------|-------------|
| `collapse_thoughts_on_complete` | `true` | Collapse `Thinking` boxes after a completed `Thoughts` event. |
| `collapse_exec_output_on_complete` | `true` | Collapse `Execution Output` boxes after a completed `CodeExecutionOutput` event. |
| `collapse_approved_code_actions` | `false` | Collapse approved code action previews after approval. |
| `collapse_approved_tool_calls` | `true` | Collapse approved tool call previews after approval. |
| `collapse_completed_subagent_tasks` | `true` | Collapse completed root-level `subagent_task` widgets after the parent task `Tool Output` arrives. |
| `collapse_tool_outputs` | `true` | Render `Tool Output` boxes collapsed by default. |
| `keep_rejected_actions_expanded` | `true` | Keep rejected action previews expanded after rejection. |
| `pin_pending_approval_action_expanded` | `true` | Keep the current pending approval action expanded until a decision is made. |
| `expand_all_toggle_key` | `ctrl+o` | Toggle all collapsible boxes between expanded and configured state. |

[^1]: [Code Mode: the better way to use MCP](https://blog.cloudflare.com/code-mode/)
