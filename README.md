# `freeact`

A lightweight library for code-action based agents.

## Introduction

`freeact` is a minimalistic agent library that empowers language models to act as autonomous agents through executable **code actions**. By enabling agents to express their actions directly in code rather than through constrained formats like JSON, `freeact` provides a flexible and powerful approach to solving complex, open-ended problems that require dynamic solution paths.

The library builds upon [recent](https://arxiv.org/abs/2402.01030) [research](https://arxiv.org/abs/2411.01747) demonstrating that code-based actions significantly outperform traditional agent approaches, with studies showing up to 20% higher success rates compared to conventional methods. While existing solutions often restrict agents to predefined tool sets, `freeact` removes these limitations by allowing agents to leverage the full power of the Python ecosystem, dynamically installing and utilizing any required libraries as needed.

## Key Capabilities

`freeact` agents can autonomously improve their actions through learning from environmental feedback, execution results, and human guidance. A prominent feature is their ability to store and reuse successful code actions as custom skills in long-term memory. These skills can be composed and interactively refined to build increasingly sophisticated capabilities, enabling efficient scaling to complex tasks.

The library's architecture emphasizes extensibility and transparency, avoiding the accidental complexity often introduced by heavier frameworks that obscure crucial implementation details. This design philosophy makes freeact particularly suitable for developers and researchers who need fine-grained control over their agent implementations while maintaining the flexibility to handle edge cases that fall outside predefined action spaces.

`freeact` executes all code actions within [`ipybox`](https://gradion-ai.github.io/ipybox/), a secure execution environment built on IPython and Docker that can also be deployed locally. This ensures safe execution of dynamically generated code while maintaining full access to the Python ecosystem. Combined with its lightweight and extensible architecture, `freeact` provides a robust foundation for building adaptable AI agents that can tackle real-world challenges requiring dynamic problem-solving approaches.

## Documentation

The `freeact` documentation is available [here](https://gradion-ai.github.io/freeact/).

## Quickstart

Install `freeact` using pip:

```bash
pip install freeact
```

Create a `.env` file with [Anthropic](https://console.anthropic.com/settings/keys) and [Gemini](https://aistudio.google.com/app/apikey) API keys:

```env title=".env"
# Required for Claude 3.5 Sonnet
ANTHROPIC_API_KEY=...

# Required for generative Google Search via Gemini 2
GOOGLE_API_KEY=...
```

Launch a `freeact` agent with generative Google Search skill using the CLI

```bash
python -m freeact.cli \
  --model-name=claude-3-5-sonnet-20241022 \
  --ipybox-tag=ghcr.io/gradion-ai/ipybox:basic \
  --skill-modules=freeact_skills.search.google.stream.api
```

or an equivalent [quickstart.py](freeact/examples/quickstart.py) script:

```python
import asyncio

from dotenv import load_dotenv
from rich.console import Console

from freeact import Claude, CodeActAgent, execution_environment
from freeact.cli.utils import stream_conversation


async def main():
    async with execution_environment(
        ipybox_tag="ghcr.io/gradion-ai/ipybox:basic",
    ) as env:
        skill_sources = await env.executor.get_module_sources(
            module_names=["freeact_skills.search.google.stream.api"],
        )

        model = Claude(model_name="claude-3-5-sonnet-20241022", logger=env.logger)
        agent = CodeActAgent(model=model, executor=env.executor)
        await stream_conversation(agent, console=Console(), skill_sources=skill_sources)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
```

Once launched, you can start interacting with the agent:

https://github.com/user-attachments/assets/83cec179-54dc-456c-b647-ea98ec99600b
