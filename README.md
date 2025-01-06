# freeact

`freeact` is a lightweight Python implementation of AI agents that use *code actions* to dynamically interact with and adapt to their environment. `freeact` agents:

- Write their actions in code, rather than just being agents for writing code
- Have a broad action space since they can install and use any Python library in their code actions
- Autonomously improve their code actions through reflection on environmental observations, execution feedback, and human input
- Store code actions as custom skills in long-term memory for efficient reuse, enabling the composition of higher-level capabilities
- Perform software-engineering tasks during the interactive development and optimization of custom agent skills
- Execute code actions in [`ipybox`](https://gradion-ai.github.io/ipybox/), a secure code execution environment built with IPython and Docker

`freeact` agents can function as general-purpose agents right out of the box—no extra tool configuration needed—or be specialized for specific environments using custom skills and system extensions:

- Custom skills provide optimized interfaces for the agent to interact with specific environments
- System extensions provide natural language configurations for custom domain knowledge and agent behavior

## Documentation

The `freeact` documentation is available [here](https://gradion-ai.github.io/freeact/).

## Quickstart

### Installation

Install `freeact` using pip:

```bash
pip install freeact
```

### Configuration

Create a `.env` file with [Anthropic](https://console.anthropic.com/settings/keys) and [Gemini](https://aistudio.google.com/app/apikey) API keys:

```env title=".env"
# Required for Claude 3.5 Sonnet
ANTHROPIC_API_KEY=...

# Required for generative Google Search via Gemini 2
GOOGLE_API_KEY=...
```

### Launch the Agent

Start a `freeact` agent with generative Google Search skill using the CLI:

```bash
python -m freeact.cli \
  --model-name=claude-3-5-sonnet-20241022 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```

Once launched, you can start interacting with the agent:

[![output](docs/tutorials/output/quickstart.svg)](docs/tutorials/output/quickstart.html)
