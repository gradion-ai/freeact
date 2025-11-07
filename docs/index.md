# Introduction

`freeact` is a lightweight AI agent library that uses Python code for defining tool interfaces and executable *code actions*.
This is in contrast to traditional approaches where tool interfaces and actions are defined in JSON.[^1]

A unified code-based approach enables `freeact` agents to reuse code actions from earlier steps as tools or *skills* in later steps. 
Agents can build upon their previous work and compose more complex code actions from simpler ones.[^2]

<figure markdown>
  [![introduction](img/introduction.png){ align="center" width="80%" }](img/introduction.png){target="_blank"}
  <figcaption>A unified code-based approach for defining actions and skills.</figcaption>
</figure>

## Overview

`freeact` agents are LLM agents that:

- generate code actions in Python and execute them in a [sandboxed environment](environment.md)
- can use any function or methods from any Python package as tool definition
- can store generated code actions as [skills in long-term memory](skills/collaborative-learning.md)
- can reuse these skills as tools in other code actions and improve on them
- support invocation and composition of [MCP tools in code actions](mcp-integration.md)

!!! Info "Supported models"

    `freeact` supports usage of any LLM from any provider as code action model via [LiteLLM](https://github.com/BerriAI/litellm).

!!! Info "Sponsored by"
    <a href="https://e2b.dev/startups" target="_blank" rel="noopener"><img src="img/sponsor.png" alt="Sponsored by E2B for Startups" width="30%"></a>

## Motivation

Most LLMs today excel at understanding and generating code. 
It is therefore a natural choice to provide agents with tool interfaces defined in Python, annotated with docstrings.
These are often defined in modules that provide the interfaces or facades for larger packages, rather than implementation details that aren't relevant for tool usage.

A code-based approach enables `freeact` agents to go beyond simple function calling. 
For example, agents can instantiate classes and use their methods for stateful processing, or [act on complex result types](skills/predefined-skills.md) that not only encapsulate data but also provide result-specific behavior via methods. 

Because tool definitions and code actions use the same programming language, tools can be natively composed. 
Another advantage is that code actions generated at one step can be reused as tools in later steps.
This allows `freeact` agents to learn from past experiences and compose more complex actions from simpler ones.
We use the term *skills* instead of *tools* throughout our documentation, to convey their greater generality.

[^1]: Code actions can significantly outperform JSON-based approaches, showing up to 20% higher success rates as shown in the [CodeAct](https://arxiv.org/abs/2402.01030) paper.
[^2]: This approach became popular with the [Voyager](https://arxiv.org/abs/2305.16291) paper where it was applied to Minecraft playing agents.
