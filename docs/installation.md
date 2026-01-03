# Installation

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 20+ (for MCP servers)

## Workspace Setup

In a directory of your choice, create a new workspace using uv:

```bash
uv init --bare --python 3.13
```

## Install Freeact

```bash
uv add freeact
```

## API Key

Freeact uses `gemini-3-flash-preview` as the default model. Set the API key in your environment:

```bash
export GEMINI_API_KEY="your-api-key"
```

Alternatively, place it in a `.env` file in the workspace directory:

```env title=".env"
GEMINI_API_KEY=your-api-key
```

## Sandbox Dependencies

For running freeact in sandbox mode, install additional dependencies:

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

## Next Steps

See the [Quickstart](quickstart.md) to run freeact and start your first conversation.
