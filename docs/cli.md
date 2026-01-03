# User Interfaces

## CLI

### Commands

Start the terminal interface:

```bash
freeact
freeact run
```

The `.freeact/` configuration directory is created automatically if it does not exist. To initialize it without starting the terminal interface:

```bash
freeact init
```

See [Configuration](configuration.md) for details.

### Options

| Option | Description |
|--------|-------------|
| `--sandbox` | Run code execution in sandbox mode using [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime). |
| `--sandbox-config PATH` | Path to sandbox configuration file. See [Sandbox Mode](sandbox.md). |
| `--log-level LEVEL` | Set logging level: `debug`, `info` (default), `warning`, `error`, `critical`. |
| `--record` | Record the conversation as SVG and HTML files. |
| `--record-dir PATH` | Output directory for recordings (default: `output`). |
| `--record-title TEXT` | Title for the recording (default: `Conversation`). |

### Environment Variables

Freeact loads environment variables from a `.env` file in the working directory. Required variables depend on [configured MCP servers](configuration.md#mcp-server-configuration). The default configuration requires:

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | API key for the default Google PTC server |

Server configurations in `.freeact/servers.json` reference environment variables using `${VAR_NAME}` syntax.

### Examples

Start with sandbox mode:

```bash
freeact --sandbox
```

Start with custom sandbox configuration:

```bash
freeact --sandbox --sandbox-config sandbox-config.json
```

Record a session for documentation:

```bash
freeact --record --record-dir docs/recordings/demo --record-title "Demo Session"
```

## Terminal Interface

The terminal interface provides interactive conversation with the agent in a terminal window.

### Input

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Option+Enter` (macOS) / `Alt+Enter` (Linux/Windows) | Insert newline |
| `q` + `Enter` | Quit |

### Image Attachments

Reference images using `@path` syntax:

```
@screenshot.png What does this show?
@images/ Describe these images
```

- Single file: `@path/to/image.png`
- Directory: `@path/to/dir/` (includes all images in directory, non-recursive)
- Supported formats: PNG, JPG, JPEG, GIF, WEBP
- Tab completion available for paths

Images are automatically downscaled if larger than 1024 pixels in either dimension.

### Approval Prompt

Before executing tool calls or code actions, the agent requests approval:

```
Approve? [Y/n/a/s]:
```

| Response | Effect |
|----------|--------|
| `Y` or `Enter` | Approve this execution |
| `n` | Reject this execution (ends the current agent turn) |
| `a` | Always approve this action (persisted to `.freeact/permissions.json`) |
| `s` | Approve for current session only |

See [Approval](features/approval.md) for details.
