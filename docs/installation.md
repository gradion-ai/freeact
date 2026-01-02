# Installation

This guide covers workspace setup, installation, and configuration of freeact.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 20+ (for MCP servers)

## Workspace Setup

Create a new workspace using uv:

```bash
uv init --bare --python 3.13
```

## Install Freeact

Add freeact to your project:

```bash
uv add freeact
```

## API Keys

Freeact uses `gemini-3-flash-preview` as the default model. Set the API key in your environment:

```bash
export GEMINI_API_KEY="your-api-key"
```

Alternatively, place it in a `.env` file in your workspace:

```env title=".env"
GEMINI_API_KEY=your-api-key
```

## Initialize Configuration

Run the init command to create the `.freeact/` configuration directory:

```bash
uv run freeact init
```

This creates:

```
.freeact/
├── prompts/
│   └── system.md        # System prompt template
├── servers.json         # MCP server configurations
├── skills/              # Agent skills
│   ├── output-parsers/
│   ├── saving-codeacts/
│   └── task-planning/
└── plans/               # Task plan storage
```

## Running the Agent

Start the interactive terminal:

```bash
uv run freeact
```

## Sandbox Mode (Optional)

Sandbox mode requires additional dependencies. See [Sandboxing](features/sandbox.md) for configuration details.

### macOS

```bash
npm install -g @anthropic-ai/sandbox-runtime@0.0.21
brew install ripgrep
```

macOS uses the native `sandbox-exec` for process isolation.

### Linux

```bash
npm install -g @anthropic-ai/sandbox-runtime@0.0.21
apt-get install bubblewrap socat ripgrep
```

!!! note
    Linux sandboxing is currently work in progress.

### Running with Sandbox

```bash
uv run freeact --sandbox
```

For custom sandbox configuration:

```bash
uv run freeact --sandbox --sandbox-config sandbox-config.json
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--sandbox` | Run code execution in sandbox mode |
| `--sandbox-config PATH` | Path to sandbox configuration file |
| `--log-level LEVEL` | Set logging level (debug, info, warning, error, critical) |
| `--record` | Record conversation as SVG and HTML files |
| `--record-dir PATH` | Recording output directory (default: output/) |
| `--record-title TITLE` | Title for the recording |

## Next Steps

- [Quickstart](quickstart.md) - Run your first task
- [Configuration](configuration.md) - Customize your setup
- [Python API](python-api.md) - Integrate freeact in your applications
