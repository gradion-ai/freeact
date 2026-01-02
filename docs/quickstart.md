# Quickstart

This guide shows how to run your first task with freeact.

## Prerequisites

Complete the [installation](installation.md) steps first:

- Set up a workspace with `uv init --bare --python 3.13`
- Install freeact with `uv add freeact`
- Initialize configuration with `uv run freeact init`

## Running a Task

Start the interactive terminal:

```bash
uv run freeact
```

Enter a task at the prompt. The agent writes Python code to accomplish it, then asks for approval before execution.

[![Terminal session](recordings/quickstart/conversation.svg)](recordings/quickstart/conversation.html){target="_blank"}

The recording above shows the agent calculating Fibonacci numbers through a code action. Key elements:

- **Code Action**: The agent writes a Python function and executes it
- **Approval**: Before running code, the agent asks for confirmation (`Y` to approve)
- **Output**: Results display directly in the terminal

## Python API

The terminal interface uses the Python API internally. Here's a minimal example that runs the same type of task programmatically:

```python
--8<-- "examples/basic_agent.py:example"
```

The API provides:

- [`Config`][freeact.agent.config.Config] for loading settings from `.freeact/`
- [`Agent`][freeact.agent.Agent] as an async context manager for running tasks
- Event types like [`ApprovalRequest`][freeact.agent.ApprovalRequest] and [`Response`][freeact.agent.Response] for handling the stream

See [Python API](python-api.md) for detailed usage.

## Next Steps

- [Programmatic Tool Calling](features/programmatic-tools.md) - Call MCP tools from code actions
- [Configuration](configuration.md) - Customize servers, skills, and prompts
- [Approval Mechanism](features/approval.md) - Understand the approval flow
