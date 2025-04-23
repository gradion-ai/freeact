# Overview

1. [Basic usage](basics.md) - Learn how to set up an agent, model, and code execution environment. This minimal setup demonstrates running generative Google searches and plotting the results.
2. [Skill development](skills.md) - Learn how to develop and improve custom skills in a conversation with the agent. The agent leverages its software engineering capabilities to support this process.
3. [System extensions](extend.md) - Learn how to define custom agent behavior and constraints through system extensions in natural language. This enables human-in-the-loop workflows, proactive agents, and more.
4. [MCP servers](mcp.md) - Learn how to use MCP servers in code actions. The execution environment can generate Python functions from MCP server metadata and use these functions in code actions.

All tutorials use a [prebuilt Docker image](../environment.md#prebuilt-docker-images) for sandboxed code execution and the `freeact` [CLI](../cli.md) for user-agent interactions. The [Basic usage](basics.md) tutorial additionally demonstrates the minimal Python code needed to implement a `freeact` agent.
