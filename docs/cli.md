# CLI

The `freeact` command provides a terminal interface for interacting with the agent.

## Commands

### run

Start the interactive terminal (default command).

```bash
freeact
freeact run
```

### init

Initialize the `.freeact/` configuration directory. Creates default configuration files from templates without overwriting existing files.

```bash
freeact init
```

See [Configuration](configuration.md) for the directory structure.

## Options

| Option | Description |
|--------|-------------|
| `--sandbox` | Run code execution in sandbox mode using [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime). |
| `--sandbox-config PATH` | Path to sandbox configuration file. See [Sandboxing](features/sandbox.md). |
| `--log-level LEVEL` | Set logging level: `debug`, `info` (default), `warning`, `error`, `critical`. |
| `--record` | Record the conversation as SVG and HTML files. |
| `--record-dir PATH` | Output directory for recordings (default: `output`). |
| `--record-title TEXT` | Title for the recording (default: `Conversation`). |

## Terminal Interface

The interactive terminal provides a conversation loop with the agent.

### Input

- **Submit**: Press `Enter` to send your message
- **Multi-line**: Press `Option+Enter` (macOS) or `Alt+Enter` (Linux/Windows) for a new line
- **Quit**: Type `q` and press `Enter` to exit

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
| `n` | Reject this execution |
| `a` | Always approve this tool (persisted to `.freeact/permissions.json`) |
| `s` | Approve for current session only |

See [Approval](features/approval.md) for details.

## Environment Variables

Freeact loads environment variables from a `.env` file in the working directory.

Required variables depend on configured servers. The default configuration requires:

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | API key for the default Google PTC server |

Server configurations in `.freeact/servers.json` reference environment variables using `${VAR_NAME}` syntax.

## Examples

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

Enable debug logging:

```bash
freeact --log-level debug
```
