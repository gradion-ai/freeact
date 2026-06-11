# Add custom tool servers

Code execution and filesystem tools are always available to the agent. This guide shows how to extend the agent's tool surface in `.freeact/config.toml`: enable bundled tool servers with one-line presets, and add custom MCP servers for programmatic tool calling (code mode) or JSON tool calling. See [Configuration](../reference/configuration.md#configuration-file) for the file basics and [Code actions](../concepts/code-actions.md#programmatic-tool-calls) for how generated tool APIs are used in code actions.

## Enable bundled servers

The `[agent.tools]` section enables bundled tool servers with one line each. Defaults are minimal: the web tool servers are off, while code execution, filesystem tools, and [basic tool discovery](tool-discovery.md) are available out of the box.

```toml title=".freeact/config.toml"
[agent.tools]
search = true            # google search (code mode); needs GEMINI_API_KEY
fetch = true             # web fetch (code mode)
```

| Preset | Default | Description |
|--------|---------|-------------|
| `search` | `false` | Adds the bundled `google` server (web search via Gemini with Google Search grounding) to [`ptc_servers`](#add-servers-for-programmatic-tool-calling). Requires `GEMINI_API_KEY`. |
| `fetch` | `false` | Adds the bundled `fetch` server (URL content retrieval via [trafilatura](https://trafilatura.readthedocs.io/){target="_blank"}) to [`ptc_servers`](#add-servers-for-programmatic-tool-calling). |

The `[agent.tools]` section also accepts a `discovery` key for enabling tool discovery; see [Configure tool discovery](tool-discovery.md).

Further bundled servers can be added manually to `ptc_servers`:

```toml title=".freeact/config.toml"
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

## Add servers for programmatic tool calling

MCP servers called programmatically via generated Python APIs are defined as `[agent.ptc_servers.<name>]` tables. This is freeact's implementation of *code mode*[^1], where the agent calls MCP tools by writing code against generated APIs rather than through JSON tool calls. This allows composing multiple tool calls, processing intermediate results, and using control flow within a single code action.

```toml title=".freeact/config.toml"
[agent.ptc_servers.github]
url = "https://api.githubcopilot.com/mcp/"
headers = { Authorization = "Bearer ${GITHUB_API_KEY}" }
```

Python APIs must be generated from `ptc_servers` to `.freeact/generated/mcptools/<server-name>/<tool>.py` before the agent can use them. The [CLI tool](../reference/cli.md) handles this automatically on start. When using the Agent SDK, call [`generate_mcp_sources()`][freeact.tools.pytools.apigen.generate_mcp_sources] explicitly, as shown in the [SDK tutorial](../getting-started/sdk-tutorial.md#3-generate-mcp-tool-apis). Code actions can then import and call the generated APIs because `.freeact/generated/` is on the kernel's `PYTHONPATH`.

## Add servers for JSON tool calling

MCP servers called directly via JSON tool calls are defined as `[agent.mcp_servers.<name>]` tables:

```toml title=".freeact/config.toml"
[agent.mcp_servers.github]
command = "docker"
args = ["run", "-i", "--rm", "-e", "GITHUB_TOKEN", "ghcr.io/github/github-mcp-server"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
exclude_tools = []
```

The optional `exclude_tools` list hides individual server tools from the agent.

Internal servers ([`filesystem`][freeact.config.FILESYSTEM_MCP_SERVER_CONFIG] for file operations and `pytools` for [basic][freeact.config.BASIC_SEARCH_MCP_SERVER_CONFIG] or [hybrid][freeact.config.HYBRID_SEARCH_MCP_SERVER_CONFIG] tool discovery) are provided automatically and do not need to be configured. User-defined servers are merged with the internal defaults. If a user entry uses the same key as an internal server, the user entry takes precedence.

## Server formats

Both `mcp_servers` and `ptc_servers` support stdio servers (`command`, `args`, `env`) and streamable HTTP servers (`url`, `headers`):

```toml title=".freeact/config.toml"
[agent.ptc_servers.github]
url = "https://api.githubcopilot.com/mcp/"
headers = { Authorization = "Bearer ${GITHUB_API_KEY}" }
```

Server configurations support [`${VAR}` environment variable references](../reference/environment.md#variable-references).

[^1]: [Code Mode: the better way to use MCP](https://blog.cloudflare.com/code-mode/)
