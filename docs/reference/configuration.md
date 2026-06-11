# Configuration

Freeact reads configuration from a single file, `.freeact/config.toml`, with an [`[agent]`](#agent-settings) and a [`[terminal]`](#terminal-ui) section. The file is human-owned: `freeact init` writes it once with commented defaults, and freeact never rewrites it afterwards. Approval decisions are stored separately in the machine-managed [`.freeact/permissions.toml`](permission-rules.md). The agent's tool surface (presets, custom MCP servers, tool discovery) is documented in [Add custom tool servers](../guides/tool-servers.md) and [Configure tool discovery](../guides/tool-discovery.md).

## Initialization

The `.freeact/` directory is initialized through CLI entry points:

| Entry Point | Description |
|-------------|-------------|
| `freeact` or<br/> `freeact run` | Initializes `.freeact/` (missing pieces only), then starts the agent. |
| `freeact init` | Initializes `.freeact/` without starting the agent. |

Initialization writes `config.toml` when missing (never overwrites), creates the runtime directories (`generated/`, `plans/`, `sessions/`), materializes [bundled skills](../guides/skills.md#bundled-skills) without overwriting user-modified ones, and seeds `permissions.toml` with the [default rules](permission-rules.md#default-rules). For programmatic configuration, see the [SDK tutorial](../getting-started/sdk-tutorial.md) and [Configuration API](../api/config.md).

## Directory Structure

Freeact stores configuration and runtime state in `.freeact/`. Project-level customization uses `AGENTS.md` for [project instructions](#project-instructions) and `.agents/skills/` for [custom skills](../guides/skills.md#add-a-custom-skill).

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
# One-line opt-ins for bundled tool servers. Code execution, filesystem tools,
# and basic tool discovery are always available by default.
# search = true            # google search (code mode); needs GEMINI_API_KEY
# fetch = true             # web fetch (code mode)
# discovery = "basic"      # default; "hybrid" needs freeact[search]; "off" disables

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
| `model` | `google-gla:gemini-3.5-flash` | [Model identifier](../guides/models.md#model-identifier) in `provider:model-name` format |
| `model_settings` | [Google thinking config](../guides/models.md#google-default) | Provider-specific [model settings](../guides/models.md#model-settings) (e.g., thinking config, temperature) |
| `provider_settings` | unset | Custom API credentials, endpoints, or other [provider-specific options](../guides/models.md#provider-settings) |
| `tools` | `discovery = "basic"`, web tools off | Presets for [bundled tool servers](../guides/tool-servers.md#enable-bundled-servers) and [tool discovery](../guides/tool-discovery.md) |
| `execution_timeout` | `300` | Maximum time in seconds for each [code execution](../concepts/code-actions.md). Approval wait time is excluded. `0` disables the timeout. |
| `approval_timeout` | `0` | Timeout in seconds for [approval requests](../concepts/approvals.md). An unresolved request is rejected when the timeout expires. `0` waits forever. |
| `tool_result_inline_max_bytes` | `32768` | Inline size threshold in bytes for tool results. Larger results are saved to `.freeact/sessions/<session-id>/tool-results/` and replaced with a file reference notice plus preview characters. |
| `tool_result_preview_chars` | `2048` | Number of preview characters included from both the beginning and end of large text results in the file reference notice. |
| `enable_persistence` | `true` | Persist message history to `.freeact/sessions/` and allow [session resume](../guides/sessions.md) with `session_id`. If `false`, history stays in memory for the process lifetime only. |
| `enable_subagents` | `true` | Whether to enable subagent delegation |
| `max_subagents` | `5` | Maximum number of concurrent subagents |
| `images_dir` | unset | Directory for saving generated images to disk. Unset defaults to `images` in the working directory; relative paths resolve against the working directory. |
| `kernel_env` | `{}` | Environment variables passed to the IPython kernel. Supports [`${VAR}` placeholders](environment.md#variable-references) resolved against the host environment. |
| `mcp_servers` | `{}` | User-defined MCP servers for [JSON tool calling](../guides/tool-servers.md#add-servers-for-json-tool-calling) |
| `ptc_servers` | `{}` | User-defined MCP servers for [programmatic tool calling](../guides/tool-servers.md#add-servers-for-programmatic-tool-calling) |

`provider_settings`, `kernel_env`, and server configurations support `${VAR}` environment variable references; see [Environment variables](environment.md#variable-references) for resolution semantics.

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
