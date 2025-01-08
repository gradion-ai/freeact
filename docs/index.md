# `freeact`

A lightweight library for code-action based agents.

## Introduction

`freeact` is a minimalistic agent library that empowers language models to act as autonomous agents through executable **code actions**. By enabling agents to express their actions directly in code rather than through constrained formats like JSON, `freeact` provides a flexible and powerful approach to solving complex, open-ended problems that require dynamic solution paths.

The library builds upon [recent](https://arxiv.org/abs/2402.01030) [research](https://arxiv.org/abs/2411.01747) demonstrating that code-based actions significantly outperform traditional agent approaches, with studies showing up to 20% higher success rates compared to conventional methods. While existing solutions often restrict agents to predefined tool sets, `freeact` removes these limitations by allowing agents to leverage the full power of the Python ecosystem, dynamically installing and utilizing any required libraries as needed.

## Key Capabilities

`freeact` agents can autonomously improve their actions through learning from environmental feedback, execution results, and human guidance. A prominent feature is their ability to store and reuse successful code actions as custom skills in long-term memory. These skills can be composed and interactively refined to build increasingly sophisticated capabilities, enabling efficient scaling to complex tasks.

The library's architecture emphasizes extensibility and transparency, avoiding the accidental complexity often introduced by heavier frameworks that obscure crucial implementation details. This design philosophy makes freeact particularly suitable for developers and researchers who need fine-grained control over their agent implementations while maintaining the flexibility to handle edge cases that fall outside predefined action spaces.

`freeact` executes all code actions within [`ipybox`](https://gradion-ai.github.io/ipybox/), a secure execution environment built on IPython and Docker that can also be deployed locally. This ensures safe execution of dynamically generated code while maintaining full access to the Python ecosystem. Combined with its lightweight and extensible architecture, `freeact` provides a robust foundation for building adaptable AI agents that can tackle real-world challenges requiring dynamic problem-solving approaches.

## Next steps

- [Quickstart](quickstart.md) - Launch your first `freeact` agent and interact with it on the command line
- [Building blocks](blocks.md) - Learn about the essential components of a `freeact` agent system
- [Tutorials](tutorials/index.md) - Tutorials demonstrating the `freeact` building blocks

## Further reading

- [Installation](installation.md) - Detailed instructions for building custom execution environments
- [Command line](cli.md) - Minimalistic command-line interface for running `freeact` agents
- [Supported models](models.md) - Models currently supported by `freeact`
- [Streaming protocol](streaming.md) - Protocol for streaming model responses and execution results

## Status

`freeact` is in an early stage of development, with ongoing development of new features. Community feedback and contributions are greatly appreciated as `freeact` continues to evolve.
