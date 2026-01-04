# Quickstart

This guide shows how to run your first task with freeact.

## Prerequisites

Complete the [installation](installation.md) steps first:

- Set up a workspace with `uv init --bare --python 3.13`
- Install freeact with `uv add freeact`
- Set your API key with `export GEMINI_API_KEY="your-api-key"` or in `.env`

## Running a Task

### Terminal Interface

Start the terminal interface:

```bash
uv run freeact
```

Enter a task at the prompt. The example below asks "who is F1 world champion 2025?" The agent generates code that calls a web search tool, with approval required before execution.

[![Terminal session](recordings/quickstart/conversation.svg)](recordings/quickstart/conversation.html){target="_blank"}

The recording above shows the agent answering "who is F1 world champion 2025?" using programmatic tool calling (PTC). Key elements:

- **Tool Discovery**: The agent progressively loads tool information: lists categories, lists tools in the `google` category, then reads the `web_search` API to understand its parameters
- **Code Action**: The agent writes Python code that imports the `web_search` tool from `mcptools.google` and calls it programmatically with the user's query
- **Approval**: Two approval prompts appear: first for the code action itself, then for the `web_search` tool call made within the code action
- **Output**: The code execution output shows the search result with source URLs, which the agent then summarizes in its response

!!! note "Pre-approved tool calls"

    Other tool calls (`pytools_*` and `filesystem_*`) have been [pre-approved](configuration.md#permissions) for this example (not shown).

### Python SDK

The terminal interface uses the freeact [Python SDK](python-api.md) internally. Here's a minimal example that runs the same task programmatically:

```python
--8<-- "examples/basic_agent.py:example"
```

See [Python SDK](python-api.md) for detailed usage.
