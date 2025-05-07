Freeact is a lightweight LLM agent library using Python as common language for describing actions and tools. This enables Freeact agents to reuse actions generated at one step as tools in later steps, so that they can learn from past experiences and compose more complex actions from simpler ones.

## Overview

Freeact agents are LLM agents that:

- generate *code actions* in Python instead of calling functions via JSON[^1]
- act by executing these code actions in a sandboxed environment
- use tools described through code and docstrings rather than JSON
- can use any feature from any Python package as tool definitions
- can compose tools in code actions with the full versatility of Python
- can store code actions as reusable *skills* in long-term memory
- can use these skills as tools in code actions and improve on them
- supports usage and composition of any MCP server tool in code actions
- supports usage of any LLM from any provider as code action generator

[^1]: Code-based actions can significantly outperform more traditional JSON-based approaches, showing up to 20% higher success rates, as shown in the following papers:

    - [Executable Code Actions Elicit Better LLM Agents](https://arxiv.org/abs/2402.01030)
    - [DynaSaur: Large Language Agents Beyond Predefined Actions](https://arxiv.org/abs/2411.01747)

## Motivation

Most LLMs today excel at understanding and generating code. 
It is therefore a natural choice to provide agents with tool specifications described in **plain Python source code**.
This is often source code of modules that provide the interfaces or facades for larger packages, rather than implementation details that aren't relevant for tool usage.
This code-based approach enables Freeact agents to go beyond simple function calling. By formulating actions as code, they can instantiate classes that are part of tool definitions, use their methods for stateful processing, or use complex result types that not only provide data but also expose behavior via methods on them. 

Because tool definitions and code actions share the same programming language, tools can be natively included and composed into code actions. 
Another advantage of this approach is that code actions generated at one step can be reused as tools in later steps.
This allows Freeact agents to learn from past experiences and compose more complex actions from simpler ones.
Because of the reusability of code actions as tools and the ability to store code actions as skills in long-term memory, we often refer to tools more generally as *skills* in the documentation and code examples.

## MCP integration

To leverage the vast ecosystem of MCP servers and their tools, Freeact automatically generates Python client functions from MCP tool definitions and provides them as *skills* to Freeact agents.
When Freeact agents use these skills in their code actions, they invoke the corresponding MCP server tool.
`stdio` based MCP servers are executed within the sandboxed environment while `sse` based MCP servers are expected to run elsewhere.

## Learning by example

Freeact agents can also leverage code snippets from tutorials, user guides, and other sources as guidance how to correctly use 3rd party Python packages in code actions.
These snippets are usually retrieved by Freeact agents themselves using skills that provide specialized search functionality.
