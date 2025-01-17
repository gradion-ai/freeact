# freeact

<p align="left">
    <a href="https://gradion-ai.github.io/freeact/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Ffreeact%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/freeact/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/freeact?color=blue"></a>
    <a href="https://github.com/gradion-ai/freeact/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/freeact"></a>
    <a href="https://github.com/gradion-ai/freeact/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/freeact/test.yml"></a>
    <a href="https://github.com/gradion-ai/freeact/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/freeact?color=blueviolet"></a>
    <a href="https://pypi.org/project/freeact/"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/freeact"></a>
</p>

A lightweight library for code-action based agents.

## Contents

- [Introduction](#introduction)
- [Key Capabilities](#key-capabilities)
- [Quickstart](#quickstart)
- [Evaluation](#evaluation)

The `freeact` documentation is available [here](https://gradion-ai.github.io/freeact/).

## Introduction

`freeact` is a lightweight agent library that empowers language models to act as autonomous agents through executable **code actions**. By enabling agents to express their actions directly in code rather than through constrained formats like JSON, `freeact` provides a flexible and powerful approach to solving complex, open-ended problems that require dynamic solution paths.

The library builds upon [recent](https://arxiv.org/abs/2402.01030) [research](https://arxiv.org/abs/2411.01747) demonstrating that code-based actions significantly outperform traditional agent approaches, with studies showing up to 20% higher success rates compared to conventional methods. While existing solutions often restrict agents to predefined tool sets, `freeact` removes these limitations by allowing agents to leverage the full power of the Python ecosystem, dynamically installing and utilizing any required libraries as needed.

## Key Capabilities

`freeact` agents can autonomously improve their actions through learning from environmental feedback, execution results, and human guidance. A prominent feature is their ability to store and reuse successful code actions as custom skills in long-term memory. These skills can be composed and interactively refined to build increasingly sophisticated capabilities, enabling efficient scaling to complex tasks.

The library's architecture emphasizes extensibility and transparency, avoiding the accidental complexity often introduced by heavier frameworks that obscure crucial implementation details. This design philosophy makes freeact particularly suitable for developers and researchers who need fine-grained control over their agent implementations while maintaining the flexibility to handle edge cases that fall outside predefined action spaces.

`freeact` executes all code actions within [`ipybox`](https://gradion-ai.github.io/ipybox/), a secure execution environment built on IPython and Docker that can also be deployed locally. This ensures safe execution of dynamically generated code while maintaining full access to the Python ecosystem. Combined with its lightweight and extensible architecture, `freeact` provides a robust foundation for building adaptable AI agents that can tackle real-world challenges requiring dynamic problem-solving approaches.

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
    asyncio.run(main())
```

Once launched, you can start interacting with the agent:

https://github.com/user-attachments/assets/83cec179-54dc-456c-b647-ea98ec99600b

## Evaluation

We [evaluated](evaluation) `freeact` using four state-of-the-art models:

- Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`)
- Claude 3.5 Haiku (`claude-3-5-haiku-20241022`)
- Gemini 2.0 Flash (`gemini-2.0-flash-exp`)
- Qwen 2.5 Coder 32B Instruct (`qwen2p5-coder-32b-instruct`)

The evaluation was performed on the [m-ric/agents_medium_benchmark_2](https://huggingface.co/datasets/m-ric/agents_medium_benchmark_2) dataset, developed by the [smolagents](https://github.com/huggingface/smolagents) team at 🤗 Hugging Face. It comprises selected tasks from GAIA, GSM8K, and SimpleQA:

[<img src="docs/eval/eval-plot.png" alt="Performance">](docs/eval/eval-plot.png)

When comparing our results with smolagents using Claude 3.5 Sonnet, we observed the following outcomes (evaluation conducted on 2025-01-07, reference data [here](https://github.com/huggingface/smolagents/blob/c22fedaee17b8b966e86dc53251f210788ae5c19/examples/benchmark.ipynb)):

[<img src="docs/eval/eval-plot-comparison.png" alt="Performance comparison" width="60%">](docs/eval/eval-plot-comparison.png)

Interestingly, these results were achieved using zero-shot prompting in `freeact`, while the smolagents implementation utilizes few-shot prompting. To ensure a fair comparison, we employed identical evaluation protocols and tools. You can find all evaluation details [here](evaluation).
