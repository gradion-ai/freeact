# CLI tool

!!! info "Work in progress"

    The [terminal interface](#interactive-mode) is preliminary and will be reimplemented in a future release.

The `freeact` or `freeact run` command starts the [interactive mode](#interactive-mode):

```bash
freeact
```

A `.freeact/` [configuration](configuration.md) directory is created automatically if it does not exist yet. The `init` subcommand initializes the configuration directory without starting the interactive mode:

```bash
freeact init
```

## Options

| Option | Description |
|--------|-------------|
| `--sandbox` | Run code execution in [sandbox mode](sandbox.md). |
| `--sandbox-config PATH` | Path to sandbox configuration file. |
| `--session-id UUID` | Resume a previous session by its UUID. Generates a new UUID if omitted. |
| `--log-level LEVEL` | Set logging level: `debug`, `info` (default), `warning`, `error`, `critical`. |

## Examples

Running code execution in [sandbox mode](sandbox.md):

```bash
freeact --sandbox
```

Running with a [custom sandbox configuration](sandbox.md#custom-configuration):

```bash
freeact --sandbox --sandbox-config sandbox-config.json
```

Resuming a previous [session](sdk.md#persistence):

```bash
freeact --session-id 550e8400-e29b-41d4-a716-446655440000
```

## Interactive Mode

The interactive mode provides a conversation interface with the agent in a terminal window.

[![Interactive Mode](screenshots/cli.png)](screenshots/cli.png){ target="_blank" rel="noopener" }

### User messages

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Ctrl+J` | Insert newline |
| `Option+Enter` (macOS)<br/>`Alt+Enter` (Linux/Windows) | Insert newline (`Ctrl+J` fallback) |
| `Ctrl+Q` | Quit |

### Clipboard

Clipboard behavior depends on terminal key forwarding.

- Paste into the prompt input: `Cmd+V` or `Ctrl+V`.
- Copy selected text from Freeact widgets: `Cmd+C` may not work in some terminals. Use `Ctrl+C` instead.
- Additional terminal fallbacks: `Ctrl+Shift+C` / `Ctrl+Insert` for copy, `Ctrl+Shift+V` / `Shift+Insert` for paste.

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

Before executing code actions or tool calls, the agent requests approval:

```
Approve? [Y/n/a/s]:
```

| Response | Effect |
|----------|--------|
| `Y` or `Enter` | Approve once |
| `n` | Reject once (ends the current agent turn) |
| `a` | Approve always (persists to `.freeact/permissions.json`) |
| `s` | Approve for current session |

See [Permissions API](sdk.md#permissions-api) for details.
