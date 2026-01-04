# CLI tool

The `freeact` or `freeact run` command starts the [interactive mode](#interactive-mode):

```bash
freeact
```

A `.freeact/` configuration directory is created automatically if it does not exist. The `init` subcommand initializes the configuration directory without starting the interactive mode:

```bash
freeact init
```

See [Configuration](configuration.md) for details.

## Options

| Option | Description |
|--------|-------------|
| `--sandbox` | Run code execution in [sandbox mode](sandbox.md). |
| `--sandbox-config PATH` | Path to sandbox configuration file. |
| `--log-level LEVEL` | Set logging level: `debug`, `info` (default), `warning`, `error`, `critical`. |
| `--record` | Record the conversation as SVG and HTML files. |
| `--record-dir PATH` | Output directory for recordings (default: `output`). |
| `--record-title TEXT` | Title for the recording (default: `Conversation`). |

## Examples

Running code execution in sandbox mode:

```bash
freeact --sandbox
```

Running with a custom sandbox configuration:

```bash
freeact --sandbox --sandbox-config sandbox-config.json
```

Recording a session for documentation:

```bash
freeact --record --record-dir docs/recordings/demo --record-title "Demo Session"
```

## Interactive Mode

The interactive mode provides a conversation interface with the agent in a terminal window.

[![Interactive mode](recordings/terminal/conversation.svg)](recordings/terminal/conversation.html){target="_blank"}

### User messages

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Option+Enter` (macOS)<br/>`Alt+Enter` (Linux/Windows) | Insert newline |
| `q` + `Enter` | Quit |

### Image Attachments

Reference images using `@path` syntax:

```
@screenshot.png What does this show?
@images/ Describe these images
```

- Single file: `@path/to/image.png`
- Directory: `@path/to/dir/` includes all images in directory, non-recursive
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

See [Permissions](configuration.md#permissions) for details.
