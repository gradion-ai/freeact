# Overview

Freeact is a lightweight, general-purpose agent that acts via [*code actions*](https://machinelearning.apple.com/research/codeact) rather than JSON tool calls[^1]. It writes executable Python code that can call multiple tools programmatically, process intermediate results, and use loops and conditionals in a single pass, which would otherwise require many inference rounds with JSON tool calling.

[Beyond executing tools](#beyond-task-execution), freeact can develop new tools from successful code actions, evolving its own tool library over time. Tools are defined via Python interfaces, progressively discovered and loaded from the agent's *workspace*[^2] rather than consuming context upfront. All execution happens locally in a secure sandbox via [ipybox](https://gradion-ai.github.io/ipybox/) and [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime).

!!! note "Supported models"

    Freeact supports models compatible with [Pydantic AI](https://ai.pydantic.dev/), with `gemini-3-flash-preview` as the current default.

## Interfaces

Freeact provides a [Python SDK](sdk.md) for application integration, and a [CLI tool](cli.md) for running the agent in a terminal.

## Features

Freeact combines the following elements into a coherent system:

| Feature | Description |
|---------|-------------|
| **Programmatic tool calling** | Agents [call tools programmatically](quickstart.md#running-a-task) within code actions rather than through JSON structures. Freeact [generates typed Python APIs](quickstart.md#generating-mcp-tool-apis) from MCP tool schemas to enable this. LLMs are heavily pretrained on Python code, making this more reliable than JSON tool calling. |
| **Reusable code actions** | Successful code actions can be [saved as discoverable tools](examples/saving-codeacts.md) with clean interfaces where function signature, data models and docstrings are separated from implementation. Agents can then use these tools in later code actions, preserving behavior as executable tools. The result is tool libraries that evolve as agents work. |
| **Agent skills** | Freeact supports the [agentskills.io](https://agentskills.io/) specification, a lightweight format for [extending agent capabilities](examples/agent-skills.md) with specialized knowledge and workflows. Freeact [provides skills](configuration.md#bundled-skills) for saving code actions as tools, enhancing existing tools, and structured task planning. |
| **Progressive loading** | Tool and skill information is [loaded in stages as needed](quickstart.md#running-a-task), rather than consuming context upfront. For tools: category names, tool names, and API definitions load progressively as needed. For skills: metadata loads at startup; full instructions load when triggered. |
| **Sandbox mode** | Code actions execute locally in a stateful IPython kernel via ipybox. [Sandbox mode](sandbox.md) restricts filesystem and network access for executed code ([example](examples/sandbox-mode.md)). Stdio MCP servers can be sandboxed independently. |
| **Unified approval** | Code actions, programmatic tool calls, and JSON-based tool calls all require approval before proceeding. [Unified approval](sdk.md#approval) ensures every action can be inspected and gated with a uniform interface regardless of how it originates. |
| **Python ecosystem** | Agents can use any Python package available in the execution environment, from data processing with `pandas` to visualization with `matplotlib` to HTTP requests with `httpx`. Many capabilities like data transformation or scientific computing don't need to be wrapped as tools when agents can [call libraries directly](examples/python-packages.md). |

## Beyond task execution

Most agents focus on either software development (coding agents) or on non-coding task execution using predefined tools, but not both. Freeact covers a wider range of this spectrum, from task execution to tool development. Its primary function is executing code actions with programmatic tool calling, guided by user instructions and custom skills. 

Beyond task execution, freeact can save successful [code actions as reusable tools](examples/saving-codeacts.md) or [enhance existing tools](examples/output-parser.md), acting as a toolsmith in its *workspace*[^2]. For heavier tool engineering like refactoring or reducing tool overlap, freeact is complemented by coding agents like Claude Code, Gemini CLI, etc. Currently the toolsmith role is interactive, with autonomous tool library evolution planned for future versions.

## LLM-friendly documentation

[^1]: Freeact also supports JSON-based tool calls on MCP servers, but mainly for internal operations.
[^2]: A workspace is an agent's working directory where it manages tools, skills, configuration and other resources.
