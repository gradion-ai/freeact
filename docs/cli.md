# CLI tool

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
| `--execution-timeout SECONDS` | Maximum time for code execution (default: 300). Approval wait time is excluded. |
| `--approval-timeout SECONDS` | Timeout for PTC approval requests (default: None, no timeout). |
| `--log-level LEVEL` | Set logging level: `debug`, `info` (default), `warning`, `error`, `critical`. |
| `--record` | Record the conversation as SVG and HTML files. |
| `--record-dir PATH` | Output directory for recordings (default: `output`). |
| `--record-title TEXT` | Title for the recording (default: `Conversation`). |

## Examples

Running code execution in [sandbox mode](sandbox.md):

```bash
freeact --sandbox
```

Running with a [custom sandbox configuration](sandbox.md#custom-configuration):

```bash
freeact --sandbox --sandbox-config sandbox-config.json
```

Recording a session for documentation:

```bash
freeact --record --record-dir docs/recordings/demo --record-title "Demo Session"
```

## Hybrid Search

Tool discovery mode is controlled by the [`tool-search`](configuration.md#tool-search) setting in `.freeact/config.json`. The default `basic` mode uses category browsing with `pytools_list_categories` and `pytools_list_tools`. Setting it to `hybrid` enables BM25/vector search with `pytools_search_tools` for natural language queries.

This requires an embedding API. The default configuration uses Gemini embeddings, which requires setting `GEMINI_API_KEY`. See [Hybrid Search](configuration.md#hybrid-search) for environment variables and customization options.

## Interactive Mode

The interactive mode provides a conversation interface with the agent in a terminal window.

[![Interactive mode](recordings/cli/conversation.svg)](recordings/cli/conversation.html){target="_blank"}

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
