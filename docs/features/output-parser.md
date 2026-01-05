# Enhancing Tools

When freeact [generates Python APIs](../quickstart.md#generating-mcp-tool-apis) from MCP tool schemas, tools that provide output schemas get a generated `Result` class with typed fields. This enables agents to chain tools in a single code action because they know the structure of intermediate results up-front.

Many MCP servers lack output schemas though. For example, the tools of the [GitHub MCP server](https://github.com/github/github-mcp-server), like `search_repositories`, `list_commits`, etc. return a JSON string without defining an output schema. 
When an MCP tool lacks an output schema, the generated Python API returns an unstructured string. 

Without knowing output structure beforehand, an agent cannot reliably write code that processes outputs inside a code action. It must retrieve raw results into context for inspection, then write processing logic in another inference round.

Output parsers solve this by augmenting tool APIs with a structured output type plus a `run_parsed()` function. With typed output information available, the agent can chain tools in a single code action because it knows the structure of intermediate results up-front. Generating an output parser must be done only once per tool, the enhancement persists across sessions.

Freeact provides the [`output-parsers`](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/output-parsers) skill for augmenting existing tools with typed output models. This is an example of the agent acting as a [toolsmith](../index.md#beyond-task-execution), enhancing its own tool library rather than just executing tasks.

## Output Parser Generation

!!! hint "Recorded session"

    A [recorded session](../recordings/reusable-codeacts-1/conversation.html) of this example is appended [below](#recording).


This example uses the [GitHub MCP server](https://github.com/github/github-mcp-server). Add it to [`ptc-servers`](../configuration.md#ptc-servers) in `.freeact/servers.json`:

```json
{
  "ptc-servers": {
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"}
    }
  }
}
```

Set your GitHub personal access token (PAT) as the `GITHUB_API_KEY` environment variable or add it to `.env`.

When starting the [CLI tool](../cli.md), Python APIs are automatically generated to `mcptools/github/`. When asked to 

> create an output parser for search_repositories

the agent, guided by the `output-parsers` skill:

1. Runs the tool with example inputs to observe output structure
2. Identifies parseable JSON with fields like `name`, `description`, `stargazers_count`
3. Adds a `ParseResult` model with typed `Repository` objects to the tool module
4. Creates a `run_parsed()` function that returns structured results
5. Saves the parser implementation to a separate `mcpparse/` module

[![Interactive mode](../recordings/reusable-codeacts-1/conversation.svg)](../recordings/reusable-codeacts-1/conversation.html){target="_blank" #recording}

The enhanced tool can now be composed with other tools in a single code action, with full type information available for processing intermediate results.
