# Overview

Freeact is a lightweight agent that acts by executing Python code and shell commands.
Code actions are key for an agent to improve its own tool library and codebase.

Freeact has a tiny core, a small system prompt, and is extensible with agent skills.
It relies on a minimal set of generic tools: read, write, execute, subagent, and tool search.

Code and shell command execution runs locally in a stateful, sandboxed environment.
Freeact supports utilization of MCP servers by generating Python APIs for their tools.

!!! note "Supported models"

    Freeact supports models compatible with [Pydantic AI](https://ai.pydantic.dev/), with `gemini-3-flash-preview` as the current default.

## Usage

| Component | Description |
|---|---|
| **[Agent SDK](sdk.md)** | Agent harness and Python API for building freeact applications. |
| **[CLI tool](cli.md)** | Terminal interface for interactive conversations with a freeact agent. |

## Capabilities

| Capability | Description |
|---|---|
| **Code actions** | Freeact agents act via Python code and shell commands. This enables tool composition and intermediate result processing in a single LLM inference pass. |
| **Local execution** | Freeact executes code and shell commands locally in an IPython kernel provided by [ipybox](https://github.com/gradion-ai/ipybox). Data, configuration and generated tools live in local workspaces.  |
| **Sandbox mode** | IPython kernels optionally run in a sandbox environment based on Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime). It enforces filesystem and network restrictions on OS-level. |
| **MCP code mode** | Freeact calls MCP server tools programmatically[^1] via generated Python APIs. This enables composition of tool calls in code actions with much lower latency. |
| **Tool discovery** | Tools are discovered via category browsing or hybrid BM25/vector search. On-demand loading frees the context window and scales to larger tool libraries. |
| **Tool authoring** | Agents can create new tools, enhance existing tools, or save code actions as reusable tools. This captures successful experience as executable knowledge. |
| **Agent skills** | Skills give agents new capabilities and expertise based on [agentskills.io](https://agentskills.io/). They compose naturally with code actions and agent-authored tools. |
| **Subagent delegation** | Tasks can be delegated to subagents, each using their own sandbox. It enables specialization and parallelization without cluttering the main agent's context. |
| **Action approval** | Fine-grained approval of code actions and (programmatic) tool calls from both main agents and subagents. Enables human control over potentially risky actions. |
| **Session persistence** | Freeact persists agent state incrementally. Persisted sessions can be resumed and serve as a record for debugging, evaluation, and improvement. |

[^1]: Freeact also supports MCP server integration via JSON tool calling but the recommended approach is programmatic tool calling.
