# freeact

<p align="left">
    <a href="https://gradion-ai.github.io/freeact/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Ffreeact%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/freeact/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/freeact?color=blue"></a>
    <a href="https://github.com/gradion-ai/freeact/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/freeact"></a>
    <a href="https://github.com/gradion-ai/freeact/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/freeact/test.yml"></a>
    <a href="https://github.com/gradion-ai/freeact/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/freeact?color=blueviolet"></a>
</p>

> [!NOTE]
> **Next generation freeact**
>
> This is the next generation of freeact, a complete rewrite. Older versions are maintained on the [0.6.x branch](https://github.com/gradion-ai/freeact/tree/0.6.x) and can be obtained with `pip install freeact<0.7`.

Freeact is a lightweight, general-purpose agent that acts via [*code actions*](https://machinelearning.apple.com/research/codeact) rather than JSON tool calls<sup>1)</sup>. It writes executable Python code that can call multiple tools programmatically, process intermediate results, and use loops and conditionals in a single pass, which would otherwise require many inference rounds with JSON tool calling.

[Beyond executing tools](#beyond-task-execution), freeact can develop new tools from successful code actions, evolving its own tool library over time. Tools are defined via Python interfaces, progressively discovered and loaded from the agent's *workspace*<sup>2)</sup> rather than consuming context upfront. All execution happens locally in a secure sandbox via [ipybox](https://github.com/gradion-ai/ipybox) and [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime).

**Supported models**: Freeact supports models compatible with [Pydantic AI](https://ai.pydantic.dev/), with `gemini-3-flash-preview` as the current default.

## Documentation

- 📚 [Documentation](https://gradion-ai.github.io/freeact/)
- 🚀 [Quickstart](https://gradion-ai.github.io/freeact/quickstart/)
- 🤖 [llms.txt](https://gradion-ai.github.io/freeact/llms.txt)
- 🤖 [llms-full.txt](https://gradion-ai.github.io/freeact/llms-full.txt)

## Interfaces

Freeact provides a [Python SDK](https://gradion-ai.github.io/freeact/sdk/) for application integration, and a [CLI tool](https://gradion-ai.github.io/freeact/cli/) for running the agent in a terminal.

## Features

Freeact combines the following elements into a coherent system:

| Feature | Description |
|---------|-------------|
| **Programmatic tool calling** | Agents [call tools programmatically](https://gradion-ai.github.io/freeact/quickstart/#running-a-task) within code actions rather than through JSON structures. Freeact [generates typed Python APIs](https://gradion-ai.github.io/freeact/quickstart/#generating-mcp-tool-apis) from MCP tool schemas to enable this. LLMs are heavily pretrained on Python code, making this more reliable than JSON tool calling. |
| **Reusable code actions** | Successful code actions can be [saved as discoverable tools](https://gradion-ai.github.io/freeact/examples/saving-codeacts/) with clean interfaces where function signature, data models and docstrings are separated from implementation. Agents can then use these tools in later code actions, preserving behavior as executable tools. The result is tool libraries that evolve as agents work. |
| **Agent skills** | Freeact supports the [agentskills.io](https://agentskills.io/) specification, a lightweight format for [extending agent capabilities](https://gradion-ai.github.io/freeact/examples/agent-skills/) with specialized knowledge and workflows. Freeact [provides skills](https://gradion-ai.github.io/freeact/configuration/#bundled-skills) for saving code actions as tools, enhancing existing tools, and structured task planning. |
| **Progressive loading** | Tool and skill information is [loaded in stages as needed](https://gradion-ai.github.io/freeact/quickstart/#running-a-task), rather than consuming context upfront. For tools: category names, tool names, and API definitions load progressively as needed. For skills: metadata loads at startup; full instructions load when triggered. |
| **Sandbox mode** | Code actions execute locally in a stateful IPython kernel via ipybox. [Sandbox mode](https://gradion-ai.github.io/freeact/sandbox/) restricts filesystem and network access for executed code ([example](https://gradion-ai.github.io/freeact/examples/sandbox-mode/)). Stdio MCP servers can be sandboxed independently. |
| **Unified approval** | Code actions, programmatic tool calls, and JSON-based tool calls all require approval before proceeding. [Unified approval](https://gradion-ai.github.io/freeact/sdk/#approval) ensures every action can be inspected and gated with a uniform interface regardless of how it originates. |
| **Delegated subagents** | Agents can delegate isolated subtasks with `subagent_task`, spawning child agents with fresh context and kernels. Child events include `agent_id` and use the same approval flow. |
| **Python ecosystem** | Agents can use any Python package available in the execution environment, from data processing with `pandas` to visualization with `matplotlib` to HTTP requests with `httpx`. Many capabilities like data transformation or scientific computing don't need to be wrapped as tools when agents can [call libraries directly](https://gradion-ai.github.io/freeact/examples/python-packages/). |

## Beyond task execution

Most agents focus on either software development (coding agents) or on non-coding task execution using predefined tools, but not both. Freeact covers a wider range of this spectrum, from task execution to tool development. Its primary function is executing code actions with programmatic tool calling, guided by user instructions and custom skills.

Beyond task execution, freeact can save successful [code actions as reusable tools](https://gradion-ai.github.io/freeact/examples/saving-codeacts/) or [enhance existing tools](https://gradion-ai.github.io/freeact/examples/output-parser/), acting as a toolsmith in its *workspace*<sup>2)</sup>. For heavier tool engineering like refactoring or reducing tool overlap, freeact is complemented by coding agents like Claude Code, Gemini CLI, etc. Currently the toolsmith role is interactive, with autonomous tool library evolution planned for future versions.

---

<sup>1)</sup> Freeact also supports JSON-based tool calls on MCP servers, but mainly for internal operations.<br>
<sup>2)</sup> A workspace is an agent's working directory where it manages tools, skills, configuration and other resources.
