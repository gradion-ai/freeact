# Reusable Code Actions

Any successful code action can be saved as a discoverable tool. This enables tool libraries that evolve as agents work. Composite code actions that chain multiple tools are a common example.

## Structured Intermediate Results

Agents compose tools more effectively when intermediate results are structured. With typed outputs, agents can chain tools in a single code action: call one tool, process its results, then pass them to another tool. Without structure, agents must return raw outputs to context for inspection before continuing.

Many MCP servers lack output schemas, returning raw JSON with undocumented structure. Freeact provides a specialized [agent skill](agent-skills.md) for augmenting existing MCP tools with typed output models, making them easier to compose.

## Saving Code Actions as Tools

Once a code action works, it can be saved as a discoverable tool. Freeact provides a specialized skill for this. The saved tool separates interface (function signature, models, docstrings) from implementation, enabling progressive discovery where agents inspect only what they need.

## Examples

### Generate Output Parser

[![Terminal session](../recordings/reusable-codeacts-1/conversation.svg)](../recordings/reusable-codeacts-1/conversation.html){target="_blank"}

The agent examines tool output, creates a `run_parsed()` function returning typed results, and saves it for reuse.

### Compose and Save Tool

[![Terminal session](../recordings/reusable-codeacts-2/conversation.svg)](../recordings/reusable-codeacts-2/conversation.html){target="_blank"}

The agent chains `search_repositories` with `list_commits`, parameterizes the workflow, and saves it to `gentools/`.

### Discover and Reuse

[![Terminal session](../recordings/reusable-codeacts-3/conversation.svg)](../recordings/reusable-codeacts-3/conversation.html){target="_blank"}

The agent finds the previously saved tool, reads its interface, and uses it like any other MCP tool.
