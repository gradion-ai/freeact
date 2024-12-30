# Overview

`freeact` is a lightweight Python implementation of AI agents that use *code actions*[^1]—snippets of executable Python code—to dynamically interact with and adapt to their environment. 

<figure markdown>
  ![logo](img/strawberry.resized.png){ width="400" style="display: block; margin: 0 auto" }
</figure>

`freeact` agents:

- Have a broad action space since they can install and use any Python library in their code actions
- Autonomously improve their code actions through reflection on environmental observations, execution feedback, and human input
- Store code actions as custom skills in long-term memory for efficient reuse, enabling the composition of higher-level capabilities
- Perform software-engineering tasks during the interactive development and optimization of custom agent skills

`freeact` agents can function as general-purpose agents right out of the box—no extra tool configuration needed—or be specialized for specific environments using custom skills and system extensions:

- Custom skills provide optimized interfaces for the agent to interact with specific environments
- System extensions provide natural language configurations for custom domain knowledge and agent behavior

## Tutorials

The best way to get started with `freeact` is to follow the tutorials after completing the [initial setup](tutorials/setup.md). 

1. [Basic usage](tutorials/basics.md) - Learn how to set up an agent, model, and code execution environment. This minimal setup demonstrates running generative Google searches and plotting the results.
2. [Custom skills](tutorials/skills.md) - Learn how to develop and improve custom skills in a conversation with the agent. The agent leverages its software engineering capabilities to support this process.
3. [System extensions](tutorials/extend.md) - Learn how to define custom agent behavior and constraints through system extensions in natural language. This enables human-in-the-loop workflows, proactive agents, and more.

All tutorials use the `freeact` [CLI](#cli) for user-agent interactions. The [Basic usage](tutorials/basics.md) tutorial additionally demonstrates the minimal Python code needed to implement a `freeact` agent.

## CLI

`freeact` provides a minimalistic command-line interface (CLI) for running agents. It is currently intended for demonstration purposes only. [Install `freeact`](installation.md) and run the following command to see all available options:

```bash
python -m freeact.cli --help
```

or check the [tutorials](#tutorials) for usage examples.

## Supported models

The following models are currently supported:

- `claude-3-5-sonnet-20241022`
- `claude-3-5-haiku-20241022`
- `gemini-2.0-flash-exp`

For most use cases, we recommend `claude-3-5-sonnet-20241022` due to its robust performance. The `gemini-2.0-flash-exp` integration allows developers to replace Gemini’s native code execution with [`ipybox`](https://gradion-ai.github.io/ipybox/)—a secure, locally deployable sandbox that supports extended execution timeouts, on-the-fly package installations, automatic plot generation, and additional features. Note that `gemini-2.0-flash-exp` support is still experimental.

## Status

`freeact` is in an early stage of development, with ongoing development of new features. Community feedback and contributions are greatly appreciated as `freeact` continues to evolve.

[^1]: Our approach draws inspiration from prior work including [TaskWeaver](https://arxiv.org/abs/2311.17541), [CodeAct](https://arxiv.org/abs/2402.01030), and [OpenHands](https://arxiv.org/abs/2407.16741). `freeact` emphasizes a lightweight, extensible codebase and straightforward Python API, making integration into any Python host application simple and practical. Another key difference is its focus on interactive development of agent skills, enabling rapid prototyping and iteration.
