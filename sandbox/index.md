# Sandbox Mode

Freeact can restrict filesystem and network access for code execution and MCP servers using [ipybox sandbox](https://gradion-ai.github.io/ipybox/sandbox/) and Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime).

Prerequisites

Check the installation instructions for [sandbox mode prerequisites](https://gradion-ai.github.io/freeact/installation/#sandbox-mode-prerequisites).

## Code Execution

### CLI Tool

The `--sandbox` option enables sandboxed code execution:

```
freeact --sandbox
```

A custom configuration file can override the [default restrictions](#default-restrictions):

```
freeact --sandbox --sandbox-config sandbox-config.json
```

### Python SDK

The `sandbox` and `sandbox_config` parameters of the Agent constructor provide the same functionality:

```
from pathlib import Path

agent = Agent(
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

sandbox-config.json

```
{
  "network": {
    "allowedDomains": ["example.org"],
    "deniedDomains": [],
    "allowLocalBinding": true
  },
  "filesystem": {
    "denyRead": ["sandbox-config.json"],
    "allowWrite": [".", "~/Library/Jupyter/", "~/.ipython/"],
    "denyWrite": ["sandbox-config.json"]
  }
}
```

This macOS-specific example configuration allows additional network access to `example.org`. Filesystem settings permit writes to `~/Library/Jupyter/` and `~/.ipython/`, which is required for running a sandboxed IPython kernel. The sandbox configuration file itself is protected from reads and writes.

## MCP Servers

MCP servers run as separate processes and are not affected by [code execution sandboxing](#code-execution). Local stdio servers can be sandboxed independently by wrapping the server command with the `srt` tool from sandbox-runtime. This applies to both `mcp-servers` and `ptc-servers` in the [MCP server configuration](https://gradion-ai.github.io/freeact/configuration/#mcp-server-configuration).

### Filesystem MCP Server

This example shows a sandboxed [filesystem MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) in the `mcp-servers` section:

.freeact/servers.json

```
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

sandbox-filesystem-mcp.json

```
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

```
uv add mcp-server-fetch
uv add "httpx[socks]>=0.28.1"
```

Then add it to the `ptc-servers` section:

.freeact/servers.json

```
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

sandbox-fetch-mcp.json

```
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
