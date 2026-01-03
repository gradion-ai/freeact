# Command Line

The `freeact` or `freeact run` command starts the [terminal interface](terminal.md):

```bash
freeact
freeact run
```

The `.freeact/` configuration directory is created automatically if it does not exist. The `init` subcommand initializes the configuration directory without starting the terminal interface:

```bash
freeact init
```

See [Configuration](configuration.md) for details.

## Options

| Option | Description |
|--------|-------------|
| `--sandbox` | Run code execution in sandbox mode using [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime). |
| `--sandbox-config PATH` | Path to sandbox configuration file. See [Sandbox Mode](sandbox.md). |
| `--log-level LEVEL` | Set logging level: `debug`, `info` (default), `warning`, `error`, `critical`. |
| `--record` | Record the conversation as SVG and HTML files. |
| `--record-dir PATH` | Output directory for recordings (default: `output`). |
| `--record-title TEXT` | Title for the recording (default: `Conversation`). |

## Examples

Running in sandbox mode:

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
