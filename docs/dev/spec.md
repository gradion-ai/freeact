# Hybrid Tool Search Specification

## Overview

This specification defines a hybrid BM25/vector search capability for freeact's tool discovery system. It provides an alternative to the existing basic search approach (`freeact.agent.tools.pytools.search.basic`) that uses semantic search to find relevant tools based on natural language queries.

## Goals

- Enable semantic tool discovery based on user intent rather than category browsing
- Combine keyword matching (BM25) with vector similarity for robust search
- Maintain real-time sync between tool directories and search index
- Provide a drop-in alternative to the basic pytools MCP server

## Non-Goals

- Replacing the basic search approach (both coexist as alternatives)
- Automatic query expansion or multi-query strategies (agent controls this)
- Exposing internal ranking scores to end users

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     Hybrid Search MCP Server                     │
│                   (freeact.agent.tools.pytools.search.hybrid)    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  File Watcher │    │   Embedder   │    │  Search DB   │       │
│  │  (watchfiles) │    │ (pydantic-ai)│    │ (SQLite+vec) │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                   │                   │                │
│         │   ┌───────────────┴───────────────┐   │                │
│         └──►│        Index Manager          │◄──┘                │
│             │  - Extract docstrings (AST)   │                    │
│             │  - Generate embeddings        │                    │
│             │  - Update FTS5 + vec tables   │                    │
│             └───────────────┬───────────────┘                    │
│                             │                                    │
│             ┌───────────────▼───────────────┐                    │
│             │       Search Engine           │                    │
│             │  - BM25 search (FTS5)         │                    │
│             │  - Vector search (sqlite-vec) │                    │
│             │  - Hybrid (RRF fusion)        │                    │
│             └───────────────────────────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
    ┌───────────┐     ┌───────────┐
    │ mcptools/ │     │ gentools/ │
    └───────────┘     └───────────┘
```

### Data Flow

1. **Startup**: MCP server performs incremental sync of `mcptools/` and `gentools/` directories
   - Scan all tool files and compute SHA256 content hashes
   - Compare hashes against stored values in database
   - Only embed/index tools with new or changed hashes
   - Remove entries for deleted tools
2. **Indexing**: For each new or changed tool with a valid docstring:
   - Extract full docstring from `run()` function
   - Generate embedding vector using configured embedding model
   - Store in SQLite database (FTS5 for text, sqlite-vec for vectors, hash for change detection)
3. **Watching**: File watcher monitors tool directories for changes
4. **Sync**: On file change, re-index affected tool(s) immediately
5. **Search**: Agent queries trigger hybrid search, returning ranked results

### Concurrency Model

Freeact uses asyncio throughout. All public async APIs must avoid blocking the event loop:

- **Database operations**: Wrap SQLite calls (blocking I/O) in `ipybox.utils.arun()` to run in a thread pool
- **File system operations**: Synchronous helpers (e.g., `scan_tools`, `extract_docstring`) should be called via `arun()` from async contexts
- **Embedding generation**: Use async pydantic-ai embedder APIs
- **File watching**: Use `watchfiles` which provides async iteration

Pure CPU operations (string manipulation, RRF score computation) on small data are acceptable inline without offloading.

## MCP Server Interface

### Server Name

`pytools` (same as basic, allowing drop-in replacement via config)

### Tools

#### `search_tools`

Search for tools matching a natural language query.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `query` | `string` | Yes | - | Natural language search query |
| `mode` | `string` | No | `"hybrid"` | Search mode: `"bm25"`, `"vector"`, or `"hybrid"` |
| `scope` | `string` | No | `"all"` | Search scope: `"all"`, `"gentools"`, or `"mcptools"` |
| `limit` | `integer` | No | `5` | Maximum number of results to return |

**Response:**

```python
list[ToolResult]
```

Where `ToolResult` is:

```python
class ToolResult(BaseModel):
    name: str           # Tool name (e.g., "create_issue")
    category: str       # Category/server name (e.g., "github")
    source: Literal["gentools", "mcptools"]
    description: str    # Full docstring from run()
    score: float        # Relevance score (0.0 to 1.0)
```

Results are ordered by descending score (most relevant first).

**Example:**

```json
// Request
{
  "query": "create an issue on GitHub",
  "mode": "hybrid",
  "limit": 3
}

// Response
[
  {
    "name": "create_issue",
    "category": "github",
    "source": "mcptools",
    "description": "Create a new issue in a GitHub repository.",
    "score": 0.92
  },
  {
    "name": "issue_write",
    "category": "github",
    "source": "mcptools",
    "description": "Create or update an issue in a repository.",
    "score": 0.85
  },
  {
    "name": "search_issues",
    "category": "github",
    "source": "mcptools",
    "description": "Search for issues across repositories.",
    "score": 0.71
  }
]
```

## Search Modes

### BM25 Search

Full-text search using SQLite FTS5 with BM25 ranking. Best for:

- Queries containing known tool names or keywords
- Exact term matching requirements

### Vector Search

Embedding similarity search using sqlite-vec. Best for:

- Conceptual queries describing capabilities
- Queries that may not match exact tool terminology

### Hybrid Search (Default)

Combines BM25 and vector search using Reciprocal Rank Fusion (RRF):

```
score(tool) = bm25_weight / (k + bm25_rank) + vec_weight / (k + vec_rank)
```

Where:
- `k` is a constant (default: 60) that controls rank sensitivity
- `bm25_weight` and `vec_weight` are configurable via server settings

## Configuration

### Server Settings

The hybrid search server accepts configuration via `servers.json`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `embedding_model` | `string` | - | Embedding model identifier (e.g., `"google-gla:gemini-embedding-001"`) |
| `database_path` | `string` | `".freeact/search.db"` | Path to SQLite database file |
| `bm25_weight` | `float` | `1.0` | Weight for BM25 results in hybrid fusion |
| `vec_weight` | `float` | `1.0` | Weight for vector results in hybrid fusion |
| `dimensions` | `integer` | Model default | Embedding vector dimensions |

### Mode Selection

Users choose between basic and hybrid search by configuring which module to run as the `pytools` MCP server in `servers.json`.

## Tool Indexing

### Indexed Content

For each tool file, the following is extracted and indexed:

- **Tool name**: Derived from filename (mcptools) or directory name (gentools)
- **Category**: Parent directory name
- **Source**: `"gentools"` or `"mcptools"`
- **Description**: Full docstring from `run()` function (including Args/Returns sections)
- **File hash**: SHA256 of source file content for change detection

### Exclusions

Tools are excluded from the index if:

- No `run()` function exists
- The `run()` function has no docstring
- The file/directory name starts with `_`

### File Watching

The server uses `watchfiles` to monitor:

- `mcptools/` directory (recursive)
- `gentools/` directory (recursive)

On file changes:

- **Created**: Extract and index the new tool
- **Modified**: Re-extract docstring, update embedding and FTS entry
- **Deleted**: Remove from index

## System Prompt Integration

The system prompt template uses conditional sections to provide appropriate workflow guidance based on the active search mode.

When hybrid search is active, the `{tool_discovery_workflow}` placeholder renders instructions for using `search_tools` instead of category browsing.

## Agent Workflow

With hybrid search, the agent's tool discovery workflow changes:

### Basic Mode (Current)

1. Call `pytools_list_categories` to enumerate categories
2. Call `pytools_list_tools` with relevant categories
3. Read tool source files to understand interfaces
4. Generate code using selected tools

### Hybrid Mode

1. Generate focused search query from user request
2. Call `pytools_search_tools` with query
3. Review ranked results with descriptions
4. Read tool source files if more detail needed
5. Generate code using selected tools

### Parallel Search Strategy

For complex requests requiring multiple tools, the agent can:

1. Identify distinct capabilities needed
2. Generate focused query for each capability
3. Call `pytools_search_tools` multiple times in parallel
4. Select appropriate tools from each result set

## Database Schema

The database uses a simplified 2-table design (consolidated from 3 tables):

### Tables

**entries_vec** (sqlite-vec virtual table):
```sql
CREATE VIRTUAL TABLE entries_vec USING vec0(
    id TEXT PRIMARY KEY,  -- "source:category:tool_name"
    embedding float[N]    -- N = configured dimensions
);
```

**entries_fts** (FTS5 virtual table with consolidated metadata):
```sql
CREATE VIRTUAL TABLE entries_fts USING fts5(
    id,                    -- indexed for tool name/category matching
    file_hash UNINDEXED,   -- for change detection
    description            -- indexed for content matching
);
```

### Embedding Text

The Index Manager computes embedding text as `"{id}: {description}"` for embedding generation. This text is not stored in the database.

### ID Format

Tool IDs follow the pattern: `{source}:{category}:{tool_name}`

Examples:
- `mcptools:github:create_issue`
- `gentools:data-processing:csv-parser`

## Server Lifecycle

The MCP server must hook database initialization and file watcher management into the MCP server lifecycle:

1. **On server start**: Initialize database, perform incremental sync (hash-based), start file watcher
2. **On server stop**: Stop file watcher, close database connections

## Dependencies

### Required Packages

- `sqlite-vec`: Vector similarity search extension for SQLite
- `watchfiles`: Async-native filesystem watching (Rust-based)
- `pydantic-ai`: Embedder abstraction for embedding generation
- `mcp`: MCP Python SDK for server implementation

### Documentation Links

- **MCP Python SDK**: https://modelcontextprotocol.io/llms.txt
- **watchfiles**: https://watchfiles.helpmanual.io/
- **pydantic-ai Embeddings**: https://ai.pydantic.dev/llms.txt

## Open Questions

_None at this time._

## References

- Prototype implementation: `/Users/martin/Development/sandbox/toolsearch/` (implementation hints only; this spec takes priority over prototype details)
- Research notes: `/Users/martin/Development/resources/notes/freeact/tool-search/`
- Existing basic search: `freeact/agent/tools/pytools/search/basic.py`
