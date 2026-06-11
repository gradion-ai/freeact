# Environment variables

## API keys

| Variable | Used by |
|----------|---------|
| `GEMINI_API_KEY` | The [default model](../guides/models.md#google-default) `google-gla:gemini-3.5-flash`, the bundled `google` search server ([`search` preset](../guides/tool-servers.md#enable-bundled-servers)), and the default [hybrid search](#hybrid-search) embedding model |
| `ANTHROPIC_API_KEY` | [Anthropic models](../guides/models.md#anthropic) (`anthropic:` prefix) |
| `OPENAI_API_KEY` | [OpenAI models](../guides/models.md#openai) (`openai:` prefix) |
| `BRAVE_API_KEY` | The bundled [`brave` search server](../guides/tool-servers.md#enable-bundled-servers) |

Other providers read their API keys from [`provider_settings`](../guides/models.md#provider-settings) via `${VAR}` references (for example `api_key = "${OPENROUTER_API_KEY}"`).

## `.env` loading

The CLI loads a `.env` file from the working directory before configuration resolution. SDK applications read from the process environment only.

## Variable references

`provider_settings`, `kernel_env`, and [server configurations](../guides/tool-servers.md#server-formats) in `.freeact/config.toml` support environment variable references using `${VAR_NAME}` syntax. [`resolve()`][freeact.config.resolve] validates that all referenced variables are set; a missing variable fails resolution with an error naming the variable.

## Kernel environment

The [`kernel_env`](configuration.md#agent-settings) setting passes environment variables to the IPython kernel. Values support `${VAR}` placeholders resolved against the host environment:

```toml title=".freeact/config.toml"
[agent.kernel_env]
MY_VAR = "${MY_VAR}"
```

## Hybrid search

When `discovery = "hybrid"` is set under `[agent.tools]`, the hybrid search server reads additional configuration from environment variables. Default values are provided for all optional variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | API key for the default embedding model |
| `PYTOOLS_DIR` | `.freeact/generated` | Base directory containing `mcptools/` and `gentools/` |
| `PYTOOLS_DB_PATH` | `.freeact/search.db` | Path to SQLite database for search index |
| `PYTOOLS_EMBEDDING_MODEL` | `google-gla:gemini-embedding-001` | Embedding model identifier |
| `PYTOOLS_EMBEDDING_DIM` | `3072` | Embedding vector dimensions |
| `PYTOOLS_SYNC` | `true` | Sync index with tool directories on startup |
| `PYTOOLS_WATCH` | `true` | Watch tool directories for changes |
| `PYTOOLS_BM25_WEIGHT` | `1.0` | Weight for BM25 (keyword) results in hybrid fusion |
| `PYTOOLS_VEC_WEIGHT` | `1.0` | Weight for vector (semantic) results in hybrid fusion |

See [Configure tool discovery](../guides/tool-discovery.md#set-up-hybrid-search) for setup steps and embedding provider options.
