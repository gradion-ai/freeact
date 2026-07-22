# Installation

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 20+ (for MCP servers)

## Workspace Setup

A workspace is a directory where freeact stores configuration, tools, and other resources. Both setup options below require their own workspace directory.

### Option 1: Minimal

The fastest way to get started is using `uvx`, which keeps the virtual environment separate from the workspace:

```
mkdir my-workspace && cd my-workspace
uvx freeact
```

This is ideal when you don't need to install additional Python packages in the workspace.

### Option 2: With Virtual Environment

To create a workspace with its own virtual environment:

```
mkdir my-workspace && cd my-workspace
uv init --bare --python 3.13
uv add freeact
```

Then run freeact with:

```
uv run freeact
```

This approach lets you install additional packages (e.g., `uv add pandas`) that will be available to the agent.

In environments managed with `pip`, install the core package with:

```
pip install freeact
```

## Hybrid Tool Discovery

[Hybrid tool discovery](https://gradion-ai.github.io/freeact/guides/tool-discovery/index.md) (`discovery = "hybrid"` in `.freeact/config.toml`) requires the `search` extra, which adds `sqlite-vec` and `watchfiles`:

```
uv add 'freeact[search]'
```

or with `pip`:

```
pip install 'freeact[search]'
```

With `uvx`, run freeact with the extra applied:

```
uvx --from 'freeact[search]' freeact
```

The core install covers everything else: SDK, CLI, bundled tool servers, and basic tool discovery.

## API Key

Freeact uses `google-gla:gemini-3.6-flash` as the [default model](https://gradion-ai.github.io/freeact/guides/models/index.md). Set the API key in your environment:

```
export GEMINI_API_KEY="your-api-key"
```

Alternatively, place it in a `.env` file in the workspace directory:

.env

```
GEMINI_API_KEY=your-api-key
```

## Sandbox Mode Prerequisites

For running freeact in sandbox mode, install Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime):

```
npm install -g @anthropic-ai/sandbox-runtime@0.0.21
```

Higher versions should also work, but 0.0.21 is the version used in current tests.

Required OS-level packages are:

### macOS

```
brew install ripgrep
```

macOS uses the native `sandbox-exec` for process isolation.

### Linux

```
apt-get install bubblewrap socat ripgrep
```

Work in progress

Sandboxing on Linux is currently work in progress.
