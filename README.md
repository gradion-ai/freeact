# freeact

<p align="left">
    <a href="https://gradion-ai.github.io/freeact/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Ffreeact%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/freeact/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/freeact?color=blue"></a>
    <a href="https://github.com/gradion-ai/freeact/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/freeact"></a>
    <a href="https://github.com/gradion-ai/freeact/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/freeact/test.yml"></a>
    <a href="https://github.com/gradion-ai/freeact/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/freeact?color=blueviolet"></a>
</p>

Freeact is a lightweight agent that acts by executing Python code and shell commands.
Code actions are key for an agent to improve its own tool library and codebase.

Freeact has a tiny core, a small system prompt, and is extensible with agent skills.
It relies on a minimal set of generic tools: read, write, execute, subagent, and tool search.

Code and shell command execution runs locally in a stateful, sandboxed environment.
Freeact supports utilization of MCP servers by generating Python APIs for their tools.

**Supported models**: Freeact supports models compatible with [Pydantic AI](https://ai.pydantic.dev/), with `gemini-3-flash-preview` as the current default.

## Documentation

- 📚 [Documentation](https://gradion-ai.github.io/freeact/)
- 🚀 [Quickstart](https://gradion-ai.github.io/freeact/quickstart/)
- 🤖 [llms.txt](https://gradion-ai.github.io/freeact/llms.txt)
- 🤖 [llms-full.txt](https://gradion-ai.github.io/freeact/llms-full.txt)

## Usage

| Component | Description |
|---|---|
| **[Agent SDK](https://gradion-ai.github.io/freeact/sdk/)** | Agent harness and Python API for building freeact applications. |
| **[CLI tool](https://gradion-ai.github.io/freeact/cli/)** | Terminal interface for interactive conversations with a freeact agent. |

## Capabilities

| Capability | Description |
|---|---|
| **Code actions** | Freeact agents act via Python code and shell commands. This enables tool composition and intermediate result processing in a single LLM inference pass. |
| **Local execution** | Freeact executes code and shell commands locally in an IPython kernel provided by [ipybox](https://github.com/gradion-ai/ipybox). Data, configuration and generated tools live in local workspaces. |
| **Sandbox mode** | IPython kernels optionally run in a sandbox environment based on Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime). It enforces filesystem and network restrictions on OS-level. |
| **MCP code mode** | Freeact calls MCP server tools programmatically via generated Python APIs. This enables composition of tool calls in code actions with much lower latency. |
| **Tool discovery** | Tools are discovered via category browsing or hybrid BM25/vector search. On-demand loading frees the context window and scales to larger tool libraries. |
| **Tool authoring** | Agents can create new tools, enhance existing tools, or save code actions as reusable tools. This captures successful experience as executable knowledge. |
| **Agent skills** | Skills give agents new capabilities and expertise based on [agentskills.io](https://agentskills.io/). They compose naturally with code actions and agent-authored tools. |
| **Subagent delegation** | Tasks can be delegated to subagents, each using their own sandbox. It enables specialization and parallelization without cluttering the main agent's context. |
| **Action approval** | Fine-grained approval of code actions and (programmatic) tool calls from both main agents and subagents. Enables human control over potentially risky actions. |
| **Session persistence** | Freeact persists agent state incrementally. Persisted sessions can be resumed and serve as a record for debugging, evaluation, and improvement. |

---

<sup>1)</sup> Freeact also supports JSON-based tool calls on MCP servers, but mainly for internal operations.<br>
<sup>2)</sup> A workspace is an agent's working directory where it manages tools, skills, configuration and other resources.
