# Overview

Freeact is a [lightweight](#design-considerations), general-purpose agent that acts via [code actions](https://machinelearning.apple.com/research/codeact) rather than JSON tool calls[^1]. It writes executable Python code that can call multiple tools, process intermediate results, or branch on conditions. Tasks that would otherwise require many inference rounds with JSON tool calling can be completed in a single pass. 

[^1]: Freeact also supports JSON-based tool calls on MCP servers, but mainly for internal operations. 

[Beyond executing tools](#beyond-task-execution), freeact can develop new tools from successful code actions, evolving its own tool library over time. All execution happens locally in a secure sandbox via [ipybox](https://gradion-ai.github.io/ipybox/). Tools are stored as Python code that can be refined and extended. Any model can be configured, with `gemini-3-flash-preview` as the current default. 

## Interfaces

Freeact provides:

- a Python API for application integration, and 
- a CLI and terminal interface for user interactions

## Features

Freeact combines the following elements into a coherent system:

| Feature | Description |
|---------|-------------|
| **[Programmatic tool calling](features/programmatic-tools.md)** | Auto-generates typed Python modules from MCP tool schemas, enabling agents to call tools programmatically within code actions rather than through JSON structures. LLMs are heavily pretrained on Python code, making this more reliable than JSON tool calling. Agents write code that calls multiple tools, processes intermediate results, and uses loops and conditionals in a single inference pass. |
| **[Reusable code actions](features/reusable-codeacts.md)** | When a code action succeeds, it can be saved as a discoverable tool with a clean interface where function signature, data models and docstrings are separated from implementation. Agents can then use these tools in later code actions, preserving successful behavior as executable tools. The result is tool libraries that evolve as agents work. |
| **[Agent skills](features/agent-skills.md)** | [Agent skills](https://agentskills.io/) are filesystem-based capability packages containing instructions, metadata, and optional resources that extend agent behavior for specific domains or workflows. Domain expertise, best practices, and procedural knowledge can be packaged once and reused automatically when relevant. Skills transform general-purpose agents into specialists. |
| **Progressive disclosure** | Tool and skill information is loaded in stages as needed, rather than consuming context upfront. This solves a scaling problem: preloading large collections wastes tokens on capabilities irrelevant for the current task. For tools, only locations are known initially; category names, tool names, and API definitions load progressively as needed. For skills, only metadata loads at startup; full instructions load when triggered. See [Programmatic tool calling](features/programmatic-tools.md) and [Agent skills](features/agent-skills.md). |
| **[Sandboxed execution](features/sandbox.md)** | Code executes in an [IPython](https://github.com/ipython/ipython) kernel with configurable filesystem and network restrictions via Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) (`srt`), and optional sandboxing of stdio MCP servers. Sandboxing enables agents to execute arbitrary code within configurable security boundaries, complemented by an approval layer that allows inspection of every MCP tool call before execution. |
| **[Task planning](features/planning.md)** | Planning and memory management are implemented as specialized agent skills that enable structured planning workflows and persistent memory of previously successful code actions. These skills enable structured task breakdown and cross-session reuse of successful code actions. |
| **[Python packages](features/python-packages.md)** | Agents can use any Python package available in the sandbox environment, from data processing with `pandas` to visualization with `matplotlib` to HTTP requests with `httpx`. Many capabilities like data transformation, file parsing, or scientific computing don't need to be wrapped as tools when agents can call libraries directly. |
| **[Unified approval](features/approval.md)** | Code actions, programmatic tool calls within code, and JSON-based MCP tool calls all flow through a unified approval mechanism that yields requests for inspection before proceeding. A single approval flow ensures every action can be inspected and gated regardless of how it originates. |

## Design considerations

Freeact is an experiment to build a highly capable code action agent with minimal framework complexity. A lightweight framework enables rapid experimentation with different code action approaches and makes the system easy to extend. As LLMs become more capable, framework components that compensate for model limitations become obsolete. Lighter frameworks can adapt more easily to this evolution. Freeact aims to find a useful complexity-capability compromise.

## Beyond task execution

Most agents focus on either software development (coding agents) or on non-coding task execution using predefined tools, but not both. Freeact covers a wider range of this spectrum, from task execution to tool development. Its primary function is executing code actions with programmatic tool calling, guided by user instructions and custom skills. 

Beyond task execution, freeact can save successful code actions as reusable tools or enhance existing tools, acting as a toolsmith. For heavier tool engineering like refactoring or reducing tool overlap, freeact is complemented by coding agents like Claude Code, Gemini CLI, etc. Currently the toolsmith role is interactive, with autonomous tool library evolution planned for future versions.
