# Sandboxed Execution

Freeact can run code execution in a sandboxed environment with restricted filesystem and network access. This uses [Anthropic's sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) via ipybox.

## Prerequisites

Before using sandbox mode, install the sandbox runtime:

```bash
# Install sandbox-runtime (provides srt command)
npm install -g @anthropic-ai/sandbox-runtime@0.0.21
```

Platform-specific requirements:

- **macOS**: `brew install ripgrep` (uses native `sandbox-exec`)
- **Linux**: `apt-get install bubblewrap socat ripgrep` (note: Linux sandboxing is work in progress)

## Basic Usage

Enable sandboxing with the `--sandbox` flag:

```bash
freeact --sandbox
```

This runs with default restrictions:

- **Allowed**: Reading all files except `.env`, writing to current directory
- **Blocked**: All external network access, `.env` file reads

## Custom Configuration

Create a JSON file to customize sandbox restrictions:

```json
--8<-- "examples/sandbox-config.json"
```

Run with your custom configuration:

```bash
freeact --sandbox --sandbox-config sandbox-config.json
```

## Configuration Options

### Network Settings

| Field | Description |
|-------|-------------|
| `allowedDomains` | Permitted hosts (supports wildcards like `*.example.com`) |
| `deniedDomains` | Explicitly blocked domains (takes precedence over allowed) |
| `allowLocalBinding` | Boolean for local port binding |
| `allowUnixSockets` | Socket paths allowed (macOS only) |

### Filesystem Settings

| Field | Description |
|-------|-------------|
| `denyRead` | Paths blocked from reading |
| `allowWrite` | Paths permitted for writing |
| `denyWrite` | Exceptions within allowed write paths |

## Example: Custom Network Restrictions

The following recording demonstrates sandboxing with custom network restrictions. The configuration allows access to `example.org` while blocking all other external domains:

[![Terminal session](../recordings/sandbox-custom/conversation.svg)](../recordings/sandbox-custom/conversation.html){target="_blank"}

Key steps in the recording:

1. **Allowed request**: Agent fetches `example.org` successfully (returns 200)
2. **Blocked request**: Agent attempts `google.com`, fails with network error
3. **Protected file**: Agent cannot read the sandbox config file itself

## MCP Server Sandboxing

The `--sandbox` flag restricts the IPython kernel where code actions execute. MCP servers run as separate processes and are not affected by this sandbox.

To sandbox an MCP server independently, wrap the server command with `srt`:

```json
{
  "mcp-servers": {
    "filesystem": {
      "command": "srt",
      "args": [
        "--sandbox-config", "server-sandbox.json",
        "npx", "-y", "@anthropic-ai/mcp-server-filesystem", "."
      ]
    }
  }
}
```

This restricts the server's filesystem and network access according to the sandbox configuration.

For detailed MCP server sandboxing examples, see the [ipybox sandbox documentation](https://gradion-ai.github.io/ipybox/sandbox/).

## Security Considerations

- Sandbox restrictions apply to the IPython kernel and wrapped MCP servers
- The agent process itself runs outside the sandbox
- Always review sandbox configurations before running untrusted code
- Use `denyRead` to protect sensitive configuration files from within sandboxed code
