# `freeact`

<p align="left">
    <a href="https://gradion-ai.github.io/freeact/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Ffreeact%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/freeact/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/freeact?color=blue"></a>
    <a href="https://github.com/gradion-ai/freeact/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/freeact"></a>
    <a href="https://github.com/gradion-ai/freeact/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/freeact/test.yml"></a>
    <a href="https://github.com/gradion-ai/freeact/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/freeact?color=blueviolet"></a>
    <a href="https://pypi.org/project/freeact/"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/freeact"></a>
</p>

## Overview

`freeact` is a lightweight AI agent library using Python as the common language to define executable actions and to describe tool capabilities to LLMs. This is in contrast to traditional approaches where actions and tool specifications are described with JSON. A unified code-based approach enables `freeact` agents to reuse actions generated in previous steps as tools or *skills* in later steps. This design allows agents to build on their previous work and compose more complex actions from simpler ones.

<p/>
<figure style="text-align: center;">
  <a href="docs/img/introduction.png" target="_blank">
    <img src="docs/img/introduction.png" alt="introduction" width="70%">
  </a>
  <br>
  <figcaption><i>A unified code-based approach for defining actions and skills.</i></figcaption>
</figure>
<p/>

`freeact` agents are LLM agents that:

- generate *code actions* in Python instead of calling functions via JSON[^2]
- act by executing these code actions in a sandboxed environment
- use tools described through code and docstrings rather than JSON
- can use any feature from any Python package as tool definitions
- can store code actions as reusable skills in long-term memory
- can use these skills as tools in code actions and improve on them
- support invocation and composition of MCP tools in code actions

### Supported models

`freeact` supports usage of any LLM from any provider as code action model via [LiteLLM](https://github.com/BerriAI/litellm).

## Documentation

- `freeact`: https://gradion-ai.github.io/freeact/
- `ipybox`: https://gradion-ai.github.io/ipybox/

## Quickstart

Place API keys for [Anthropic](https://console.anthropic.com/settings/keys) and [Gemini](https://aistudio.google.com/app/apikey) in a `.env` file:

```env
# For Claude 3.7. Sonnet
ANTHROPIC_API_KEY=...

# For Gemini with search tool
GEMINI_API_KEY=...
```

Add MCP server data to an `mcp.json` file:

```json
{
    "mcpServers": {
        "pubmed": {
            "command": "uvx",
            "args": ["--quiet", "pubmedmcp@0.1.3"],
            "env": {"UV_PYTHON": "3.12"}
        }
    }
}
```

Start an agent with [`uvx`](https://docs.astral.sh/uv/) via the `freeact` CLI:

```bash
uvx freeact \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --model-name=anthropic/claude-3-7-sonnet-20250219 \
  --reasoning-effort=low \
  --skill-modules=freeact_skills.search.google.stream.api \
  --mcp-servers=mcp.json
```

Then have a conversation with the agent:

![output](docs/output/quickstart/conversation.svg)
