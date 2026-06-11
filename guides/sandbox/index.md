# Use sandbox mode

Freeact can restrict filesystem and network access for [code execution](https://gradion-ai.github.io/freeact/concepts/code-actions/index.md) and MCP servers using [ipybox sandbox](https://gradion-ai.github.io/ipybox/sandbox/) and Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime).

Prerequisites

Check the installation instructions for [sandbox mode prerequisites](https://gradion-ai.github.io/freeact/getting-started/installation/#sandbox-mode-prerequisites).

## Sandbox code execution

Scope

Sandbox restrictions apply equally to Python code and shell commands, as both [execute](https://gradion-ai.github.io/freeact/concepts/code-actions/index.md) in the same IPython kernel.

### CLI tool

The `--sandbox` option enables sandboxed code execution:

```
freeact --sandbox
```

A custom configuration file can override the [default restrictions](#default-restrictions):

```
freeact --sandbox --sandbox-config sandbox-config.json
```

### Agent SDK

The `sandbox` and `sandbox_config` parameters of the Agent constructor provide the same functionality:

```
from pathlib import Path

agent = Agent(
    runtime,
    sandbox=True,
    sandbox_config=Path("sandbox-config.json"),
)
```

### Default restrictions

Without a custom configuration file, sandbox mode applies these defaults:

- **Filesystem**: Read all files except `.env`, write to current directory and subdirectories
- **Network**: Internet access blocked, local network access to tool execution server permitted

### Custom configuration

Create a sandbox configuration file in your workspace directory:

sandbox-config.json

```
{
  "allowPty": true,
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

This macOS-specific example configuration allows additional network access to `example.org`. The `allowLocalBinding` setting and write access to `~/Library/Jupyter/` and `~/.ipython/` are required for running a sandboxed IPython kernel on macOS. The sandbox configuration file itself is protected from reads and writes.

### Verify the restrictions

Start the CLI tool with the custom sandbox configuration:

```
uvx freeact --sandbox --sandbox-config sandbox-config.json
```

The screenshot [below](#recording) demonstrates the sandbox in action. First, the agent can access the allowed domain:

> use requests to read from example.org, print status code only

This succeeds with status `200`. Other domains are blocked:

> now from google.com

This fails with a `403 Forbidden`. The sandbox also protects the config file:

> print the content of sandbox-config.json in a code action

This fails with a `PermissionError`.

## Sandbox MCP servers

MCP servers run as separate processes and are not affected by [code execution sandboxing](#sandbox-code-execution). Local stdio servers can be sandboxed independently by wrapping the server command with the `srt` tool from sandbox-runtime. This applies to both [`mcp_servers`](https://gradion-ai.github.io/freeact/guides/tool-servers/#add-servers-for-json-tool-calling) and [`ptc_servers`](https://gradion-ai.github.io/freeact/guides/tool-servers/#add-servers-for-programmatic-tool-calling) in the [configuration file](https://gradion-ai.github.io/freeact/reference/configuration/#configuration-file).

### Fetch MCP server

This example shows a sandboxed [fetch MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch). First, install it locally with:

```
uv add mcp-server-fetch
uv add "httpx[socks]>=0.28.1"
```

Then add it to the [`ptc_servers`](https://gradion-ai.github.io/freeact/guides/tool-servers/#add-servers-for-programmatic-tool-calling) section:

.freeact/config.toml

```
[agent.ptc_servers.fetch]
command = "srt"
args = ["--settings", "sandbox-fetch-mcp.json", "python", "-m", "mcp_server_fetch"]
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
