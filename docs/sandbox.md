# Sandbox Mode

Freeact can restrict filesystem and network access for [code execution](execution.md) and MCP servers using [ipybox sandbox](https://gradion-ai.github.io/ipybox/sandbox/) and Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime).

!!! hint "Prerequisites"

    Check the installation instructions for [sandbox mode prerequisites](installation.md#sandbox-mode-prerequisites).

## Code Execution

!!! info "Scope"

    Sandbox restrictions apply equally to Python code and shell commands, as both [execute](execution.md) in the same IPython kernel.

### CLI Tool

The `--sandbox` option enables sandboxed [code execution](execution.md):

```bash
freeact --sandbox
```

A custom configuration file can override the [default restrictions](#default-restrictions):

```bash
freeact --sandbox --sandbox-config sandbox-config.json
```

### Agent SDK

The `sandbox` and `sandbox_config` parameters of the [`Agent`][freeact.agent.Agent] constructor provide the same functionality:

```python
from pathlib import Path

agent = Agent(
    "main",
    ...
    sandbox=True,
    sandbox_config=Path("sandbox-config.json"),
)
```

### Default Restrictions

Without a custom configuration file, sandbox mode applies these defaults:

- **Filesystem**: Read all files except `.env`, write to current directory and subdirectories
- **Network**: Internet access blocked, local network access to tool execution server permitted

### Custom Configuration

```json title="sandbox-config.json"
--8<-- "examples/sandbox-config.json"
```

This macOS-specific example configuration allows additional network access to `example.org`. Filesystem settings permit writes to `~/Library/Jupyter/` and `~/.ipython/`, which is required for running a sandboxed IPython kernel. The sandbox configuration file itself is protected from reads and writes.

## MCP Servers

MCP servers run as separate processes and are not affected by [code execution sandboxing](#code-execution). Local stdio servers can be sandboxed independently by wrapping the server command with the `srt` tool from sandbox-runtime. This applies to both [`mcp-servers`](configuration.md#mcp-servers) and [`ptc-servers`](configuration.md#ptc-servers) in the [configuration file](configuration.md#configuration-file).

### Filesystem MCP Server

This example shows a sandboxed [filesystem MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) in the `mcp-servers` section:

```json title=".freeact/config.json"
{
  "mcp-servers": {
    "filesystem": {
      "command": "srt",
      "args": [
        "--settings", "sandbox-filesystem-mcp.json",
        "npx", "-y", "@modelcontextprotocol/server-filesystem", "."
      ]
    }
  }
}
```

The sandbox configuration blocks `.env` reads and allows network access to the npm registry, which is required for `npx` to download the server package:

```json title="sandbox-filesystem-mcp.json"
{
  "filesystem": {
    "denyRead": [".env"],
    "allowWrite": [".", "~/.npm"],
    "denyWrite": []
  },
  "network": {
    "allowedDomains": ["registry.npmjs.org"],
    "deniedDomains": [],
    "allowLocalBinding": true
  }
}
```

### Fetch MCP Server

This example shows a sandboxed [fetch MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch). First, install it locally with:

```bash
uv add mcp-server-fetch
uv add "httpx[socks]>=0.28.1"
```

Then add it to the `ptc-servers` section:

```json title=".freeact/config.json"
{
  "ptc-servers": {
    "fetch": {
      "command": "srt",
      "args": [
        "--settings", "sandbox-fetch-mcp.json",
        "python", "-m", "mcp_server_fetch"
      ]
    }
  }
}
```

The sandbox configuration blocks `.env` reads and restricts the MCP server to fetch only from `example.com`. Access to the npm registry is required for the server's internal operations:

```json title="sandbox-fetch-mcp.json"
{
  "filesystem": {
    "denyRead": [".env"],
    "allowWrite": [".", "~/.npm", "/tmp/**", "/private/tmp/**"],
    "denyWrite": []
  },
  "network": {
    "allowedDomains": ["registry.npmjs.org", "example.com"],
    "deniedDomains": [],
    "allowLocalBinding": true
  }
}
```
