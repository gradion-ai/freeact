# Enhancing Tools

Many MCP servers lack output schemas. For example, all tools of the [GitHub MCP server](https://github.com/github/github-mcp-server) return a JSON string without defining an output schema. Without an output schema, the `run()` function of the [generated tool API](../quickstart.md#generating-mcp-tool-apis) returns a plain string instead of a structured `Result` type.

Without knowing output structure beforehand, an agent cannot reliably write code that processes tool output inside a code action. It must retrieve raw results into context for inspection, then write processing logic in another inference round.

Freeact's bundled [`output-parsers`](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/output-parsers) skill solves this by generating output parsers that enhance tool APIs with a `run_parsed()` function that returns a structured output type. With output types known, the agent can generate processing logic in a single inference round. 

This tool enhancement persists across sessions and is an example of the agent acting as a [toolsmith](../index.md#beyond-task-execution), enhancing its own tool library rather than just executing tasks.

## Output Parser Generation

!!! hint "Recorded session"

    A [recorded session](../recordings/output-parser/conversation.html) of this example is appended [below](#recording).

Create a [workspace](../installation.md#option-1-minimal) and initialize the configuration directory:

```bash
mkdir my-workspace && cd my-workspace
uvx freeact init
```

Add the [GitHub MCP server](https://github.com/github/github-mcp-server) to [`ptc-servers`](../configuration.md#ptc-servers) in `.freeact/config.json`:

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

Then start the [CLI tool](../cli.md) to automatically generate Python APIs to `.freeact/generated/mcptools/github/`:

```bash
uvx freeact
```

When asked to 

> create an output parser for search_repositories

the agent 

1. Loads the `output-parsers` skill and the [generated](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/mcptools/github/search_repositories_orig.py) `search_repositories.py` tool API
2. Calls the `search_repositories.run()` function with example inputs to observe outputs
3. Identifies parseable JSON with fields like `name`, `description`, `stargazers_count`, etc.
4. Creates an [enhanced](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/mcptools/github/search_repositories.py) tool API with `ParseResult`, `Repository` and `run_parsed()`
5. Saves the [parser](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/mcpparse/github/search_repositories.py) to a separate `.freeact/generated/mcpparse/github/search_repositories.py`
6. Resets the IPython kernel to re-import the tool for testing `run_parsed()`

[![Interactive mode](../recordings/output-parser/conversation.svg)](../recordings/output-parser/conversation.html){target="_blank" #recording}

The enhanced tool can now be [composed with other tools](saving-codeacts.md#compose-and-save) in a single code action, with full type information available for processing intermediate results.
