# Installation

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 20+ (for MCP servers)

## Workspace Setup

A workspace is a directory where freeact stores configuration, tools, and other resources. Both setup options below require their own workspace directory.

### Option 1: Minimal

The fastest way to get started is using `uvx`, which keeps the virtual environment separate from the workspace:

```bash
mkdir my-workspace && cd my-workspace
uvx freeact
```

This is ideal when you don't need to install additional Python packages in the workspace.

### Option 2: With Virtual Environment

To create a workspace with its own virtual environment:

```bash
mkdir my-workspace && cd my-workspace
uv init --bare --python 3.13
uv add freeact
```

Then run freeact with:

```bash
uv run freeact
```

This approach lets you install additional packages (e.g., `uv add pandas`) that will be available to the agent.

## API Key

Freeact uses `gemini-3-flash-preview` as the default model. Set the API key in your environment:

```bash
export GEMINI_API_KEY="your-api-key"
```

Alternatively, place it in a `.env` file in the workspace directory:

```env title=".env"
GEMINI_API_KEY=your-api-key
```

## Sandbox Mode Prerequisites

For running freeact in sandbox mode, install Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime):

```bash
npm install -g @anthropic-ai/sandbox-runtime@0.0.21
```

Higher versions should also work, but 0.0.21 is the version used in current tests. 

Required OS-level packages are:

### macOS

```bash
brew install ripgrep
```

macOS uses the native `sandbox-exec` for process isolation.

### Linux

```bash
apt-get install bubblewrap socat ripgrep
```

!!! note
    Sandboxing on Linux is currently work in progress.
