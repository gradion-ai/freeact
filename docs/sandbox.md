# Sandbox Mode

Freeact can restrict filesystem and network access for code execution and MCP servers using Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) via [ipybox](https://gradion-ai.github.io/ipybox/). See [Installation](installation.md#sandbox-dependencies) for prerequisites.

## Code Execution Sandbox

### CLI

Enable sandboxing with the `--sandbox` flag:

```bash
freeact --sandbox
```

Run with a custom configuration file:

```bash
freeact --sandbox --sandbox-config sandbox-config.json
```

### Python API

The `sandbox` and `sandbox_config` parameters enable sandboxed code execution:

```python
from pathlib import Path

agent = Agent(
    model=config.model,
    model_settings=config.model_settings,
    system_prompt=config.system_prompt,
    mcp_servers=config.mcp_servers,
    sandbox=True,
    sandbox_config=Path("sandbox-config.json"),
)
```

### Default Restrictions

Without a custom configuration file, sandbox mode applies these defaults:

- **Filesystem**: Read all files except `.env`, write to current directory and subdirectories
- **Network**: Internet access blocked, local network access to tool execution server permitted

## Custom Configuration

Create a JSON file to customize sandbox restrictions:

```json
--8<-- "examples/sandbox-config.json"
```

The `network` section controls domain access and local port binding. The `filesystem` section controls read and write permissions with allow and deny lists. Path patterns support `~` for home directory expansion.

For all configuration options, see the [ipybox sandbox documentation](https://gradion-ai.github.io/ipybox/sandbox/) and [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime).

## MCP Server Sandbox

The `--sandbox` flag restricts the IPython kernel where code actions execute. MCP servers run as separate processes and are not affected by this sandbox.

To sandbox a stdio MCP server independently, wrap the server command with `srt`:

```json
{
  "mcp-servers": {
    "filesystem": {
      "command": "srt",
      "args": [
        "--settings", "mcp-server-sandbox-config.json",
        "npx", "-y", "@modelcontextprotocol/server-filesystem", "."
      ]
    }
  }
}
```

This restricts the server's filesystem and network access according to the sandbox configuration.

For detailed MCP server sandboxing examples, see the [ipybox sandbox documentation](https://gradion-ai.github.io/ipybox/sandbox/).
