# Configure tool discovery

The agent discovers Python tools in [tool directories](#tool-directories) under `.freeact/generated/`, loading only task-relevant tool information into the context window. Basic discovery is on by default; the mode is controlled with the `discovery` key under `[agent.tools]` in `.freeact/config.toml` (`"off"` disables it).

## Choose a discovery mode

.freeact/config.toml

```
[agent.tools]
discovery = "basic"      # default; "hybrid" needs freeact[search]; "off" disables
```

| Mode       | Description                                                                 |
| ---------- | --------------------------------------------------------------------------- |
| `"basic"`  | Category browsing with `pytools_list_categories` and `pytools_list_tools`   |
| `"hybrid"` | BM25/vector search with `pytools_search_tools` for natural language queries |

Basic mode requires no additional dependencies. Hybrid mode adds semantic search and scales to larger tool libraries.

## Set up hybrid search

1. Install the `freeact[search]` extra as described in [Installation](https://gradion-ai.github.io/freeact/getting-started/installation/#hybrid-tool-discovery). [Resolving](https://gradion-ai.github.io/freeact/api/config/index.md) a config with `discovery = "hybrid"` fails with an install hint when the extra is missing.

1. Set `GEMINI_API_KEY` in your environment. The default embedding model is `google-gla:gemini-embedding-001`.

1. Set `discovery = "hybrid"` under `[agent.tools]`:

   .freeact/config.toml

   ```
   [agent.tools]
   discovery = "hybrid"
   ```

The hybrid search server reads additional configuration from `PYTOOLS_*` environment variables, with defaults for all optional variables (index database path, sync and watch behavior, BM25/vector fusion weights). See [Environment variables](https://gradion-ai.github.io/freeact/reference/environment/#hybrid-search) for the full table.

To use a different embedding provider, set `PYTOOLS_EMBEDDING_MODEL` to a supported [pydantic-ai embedder](https://ai.pydantic.dev/embeddings/) identifier.

Testing without an API key

Set `PYTOOLS_EMBEDDING_MODEL=test` to use a test embedder that generates deterministic embeddings. This is useful for development and testing but produces meaningless search results.

## Tool directories

The agent discovers tools from two directories under `.freeact/generated/`:

### `mcptools/`

Generated Python APIs from [`ptc_servers`](https://gradion-ai.github.io/freeact/guides/tool-servers/#add-servers-for-programmatic-tool-calling) schemas:

```
.freeact/generated/mcptools/
└── <server-name>/
    └── <tool>.py        # Generated tool module
```

### `gentools/`

User-defined tools saved from successful code actions (see [Save code actions as tools](https://gradion-ai.github.io/freeact/guides/saving-tools/index.md)):

```
.freeact/generated/gentools/
└── <category>/
    └── <tool>/
        ├── __init__.py
        ├── api.py       # Public interface
        └── impl.py      # Implementation
```
