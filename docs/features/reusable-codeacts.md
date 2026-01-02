# Reusable Code Actions

When a code action succeeds, freeact can save it as a discoverable tool with a clean interface. The agent can then use these saved tools in later sessions, building a library of reusable code actions that evolve as the agent works.

## How It Works

Reusable code actions follow a three-phase workflow:

1. **Parse outputs**: Generate typed output parsers for tools that lack structured schemas
2. **Compose and save**: Chain multiple tools into a single code action and save it as a tool
3. **Discover and reuse**: In new sessions, discover and use saved tools like native MCP tools

Each saved tool creates a package in `gentools/` with separate interface and implementation modules, enabling progressive disclosure where the agent inspects only interfaces without loading full implementations.

## Session 1: Generate Output Parser

The first session demonstrates how the agent generates a typed output parser for an MCP tool.

[![Terminal session](../recordings/reusable-codeacts-1/conversation.svg)](../recordings/reusable-codeacts-1/conversation.html){target="_blank"}

Key steps:

1. **Tool exploration**: Agent discovers `search_repositories` in the `github` category
2. **Output analysis**: Agent executes the tool and examines the raw output structure
3. **Parser generation**: Agent creates a `run_parsed()` function that returns typed results
4. **Persistence**: Parser is saved to `mcpparse/github/search_repositories/`

The parser separates output transformation logic from the tool interface. The agent can now call `search_repositories.run_parsed()` to get structured results instead of raw dictionaries.

## Session 2: Compose and Save Tool

The second session shows the agent composing multiple tools and saving the composition as a reusable tool.

[![Terminal session](../recordings/reusable-codeacts-2/conversation.svg)](../recordings/reusable-codeacts-2/conversation.html){target="_blank"}

Key steps:

1. **Structured inputs**: Agent uses the parsed `search_repositories` from session 1
2. **Tool composition**: Agent chains `search_repositories` with `list_commits`
3. **Parameterization**: Agent extracts common parameters into a clean function signature
4. **Save as tool**: Agent saves the composed action to `gentools/`

The saved tool encapsulates the full workflow: search for a repository, extract its details, then fetch recent commits. Future sessions can use this as a single operation.

## Session 3: Tool Discovery and Reuse

The third session demonstrates how saved tools are discovered and used in new contexts.

[![Terminal session](../recordings/reusable-codeacts-3/conversation.svg)](../recordings/reusable-codeacts-3/conversation.html){target="_blank"}

Key steps:

1. **Category listing**: Agent lists available tool categories including `gentools/`
2. **Tool discovery**: Agent finds the previously saved tool
3. **Interface inspection**: Agent reads the `api.py` to understand parameters and return types
4. **Direct usage**: Agent imports and calls the tool like any other MCP tool

The agent treats saved code actions identically to auto-generated MCP tool APIs, enabling seamless composition of custom and standard tools.

## Directory Structure

Saved code actions and output parsers are stored in dedicated directories:

```
gentools/                          # Saved code actions
└── <category>/
    └── <tool_name>/
        ├── api.py                 # Interface: function signature, models, docstrings
        └── impl.py                # Implementation: actual code logic

mcpparse/                          # Output parsers for MCP tools
└── <server>/
    └── <tool_name>/
        ├── api.py                 # Interface: run_parsed() signature, output models
        └── impl.py                # Implementation: parsing logic
```

Keeping implementation separate from interface prevents polluting the interfaces that the agent inspects. When discovering tools, the agent reads only `api.py` files to understand what tools do and how to call them.

## Interface vs Implementation

Each saved tool has two modules:

**api.py** - The interface file contains:

- Function signature with type hints
- Pydantic models for inputs and outputs
- Docstrings describing behavior

**impl.py** - The implementation file contains:

- Actual code logic
- Imports and dependencies
- Internal helper functions

This separation supports progressive disclosure: the agent loads implementation details only when executing a tool, not when browsing available tools.

## Integration with Planning

Reusable code actions integrate with [task planning](planning.md):

- Plans can reference saved tools by name
- Tool discovery happens during plan creation
- Successfully executed plan steps can be saved as new tools
- Saved tools appear in future plans when relevant

The combination of planning and reusable code actions enables agents to build domain-specific tool libraries incrementally.

## Cross-Session Memory

Code actions saved to `gentools/` persist across sessions:

- Tools remain available after agent restarts
- Multiple sessions can contribute tools to the same library
- Tools can compose other saved tools, building layers of abstraction
- The library evolves as the agent encounters new tasks

This forms a persistent memory layer where successful behaviors are captured as executable tools rather than conversation history.
