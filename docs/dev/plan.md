# Hybrid Tool Search - Project Plan

This plan breaks down the implementation of the hybrid tool search feature into steps sized for individual Claude Code sessions.

## Progress

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 1 | Database Module | Done | |
| 2 | Docstring Extraction | Done | |
| 3 | Search Engine | Done | |
| 4 | Embedder Integration | Done | Upgraded pydantic-ai to >=1.51.0 |
| 5 | Indexer | Done | Renamed from IndexManager; added tool_info_from_path utility |
| 6 | File Watcher | Done | ToolWatcher class with 300ms debounce; .py-only filtering |
| 7 | Server Implementation | Done | FastMCP server with env config; PYTOOLS_SYNC/WATCH options |
| 8 | Package Structure | Done | Entry point via `python -m freeact.agent.tools.pytools.search.hybrid` |
| 9 | System Prompt Updates | Not Started | |
| 10 | Configuration Support | Not Started | |
| 11 | End-to-End Testing | Done | Covered by test_server.py integration tests |
| 12 | Documentation and Cleanup | Not Started | |

**Status legend**: Not Started | In Progress | Done | Blocked

## Phase 1: Core Infrastructure

### Step 1: Database Module

**Goal**: Implement the SQLite database with FTS5 and sqlite-vec support.

**Deliverables**:
- `freeact/agent/tools/pytools/search/hybrid/database.py`
- Database class with async context manager
- Tables: `tools` (metadata + hash), `entries_vec`, `entries_fts`
- CRUD operations: `add`, `update`, `delete`, `get`, `exists`
- File hash storage and comparison for change detection

**Tests**:
- `tests/unit/tools/pytools/search/hybrid/test_database.py`

**Reference**: Prototype `toolsearch/database.py`

---

### Step 2: Docstring Extraction

**Goal**: Extract full docstrings from `run()` functions using AST.

**Deliverables**:
- `freeact/agent/tools/pytools/search/hybrid/extract.py`
- `extract_docstring(filepath: Path) -> str | None` - extract from single file
- `scan_tools(base_dir: Path) -> list[ToolInfo]` - scan mcptools/ and gentools/
- `ToolInfo` dataclass with name, category, source, filepath, docstring

**Tests**:
- `tests/unit/tools/pytools/search/hybrid/test_extract.py`
- Test fixtures with sample tool files

**Reference**: Prototype `toolsearch/descriptions.py`

---

### Step 3: Search Engine

**Goal**: Implement BM25, vector, and hybrid search with RRF fusion.

**Deliverables**:
- `freeact/agent/tools/pytools/search/hybrid/search.py`
- `bm25_search(query, limit) -> list[SearchResult]`
- `vector_search(embedding, limit) -> list[SearchResult]`
- `hybrid_search(query, embedding, limit, weights) -> list[SearchResult]`
- `SearchResult` dataclass with id, score
- RRF fusion implementation

**Tests**:
- `tests/unit/tools/pytools/search/hybrid/test_search.py`

**Reference**: Prototype `toolsearch/database.py` (search methods)

---

## Phase 2: Indexing Pipeline

### Step 4: Embedder Integration

**Goal**: Integrate pydantic-ai embedder for generating tool embeddings.

**Deliverables**:
- `freeact/agent/tools/pytools/search/hybrid/embed.py`
- `ToolEmbedder` class wrapping pydantic-ai's `Embedder`
- `embed_query(text) -> list[float]` - query embedding (asymmetric)
- `embed_documents(texts) -> list[list[float]]` - batch document embedding
- Configurable model and dimensions via constructor

**Tests**:
- `tests/unit/tools/pytools/search/hybrid/test_embed.py` (mocked embedder)
- `tests/integration/tools/pytools/search/hybrid/test_embed.py` (real API, optional)

---

### Step 5: Indexer

**Goal**: Orchestrate extraction, embedding, database updates, and file watching.

**Deliverables**:
- `freeact/agent/tools/pytools/search/hybrid/index.py`
- `Indexer` class - coordinates database, embedder, scanner, and watcher
- `start() -> SyncResult` - sync and optionally start file watcher
- `stop()` - stop file watcher
- Context manager support (`async with Indexer(...) as indexer`)
- `watching: bool` constructor arg to enable/disable file watching
- `SyncResult` dataclass with added/updated/deleted counts
- SHA256 file hashing for change detection
- `tool_info_from_path()` utility in extract.py for shared path-to-ToolInfo conversion

**Tests**:
- `tests/unit/tools/pytools/search/hybrid/test_index.py`
- `tests/unit/tools/pytools/search/hybrid/test_extract.py` (tool_info_from_path tests)

---

### Step 6: File Watcher

**Goal**: Real-time monitoring of tool directories with watchfiles.

**Deliverables**:
- `freeact/agent/tools/pytools/search/hybrid/watch.py`
- `ToolWatcher` class with async context manager
- Watch mcptools/ and gentools/ recursively
- Handle created/modified/deleted events
- Debounce rapid changes
- Wire into Indexer (called from start() when watching=True)

**Tests**:
- `tests/unit/tools/pytools/search/hybrid/test_watch.py`

**Reference**: Prototype `toolsearch/fswatch.py`

---

## Phase 3: MCP Server

### Step 7: Server Implementation ✓

**Goal**: Implement the hybrid search MCP server with FastMCP.

**Deliverables**:
- `freeact/agent/tools/pytools/search/hybrid/server.py`
- `search_tools` tool with query, mode, limit parameters
- `ToolResult` response model with name, category, source, description, score
- Server lifecycle via FastMCP lifespan context manager
- Environment variable configuration:
  - `PYTOOLS_DIR` - base directory for tools
  - `PYTOOLS_DB_PATH` - SQLite database path
  - `PYTOOLS_EMBEDDING_MODEL` - embedding model (supports "test" for testing)
  - `PYTOOLS_EMBEDDING_DIM` - embedding dimensions
  - `PYTOOLS_SYNC` - enable/disable initial sync (default: true)
  - `PYTOOLS_WATCH` - enable/disable file watching (default: true)
  - `PYTOOLS_BM25_WEIGHT` / `PYTOOLS_VEC_WEIGHT` - search weights

**Tests**:
- `tests/unit/tools/pytools/search/hybrid/test_server.py` - unit tests with mocked components
- `tests/integration/tools/pytools/search/hybrid/test_server.py` - real MCP client tests via MCPServerStdio
- Test fixtures in `tests/integration/tools/pytools/search/hybrid/fixtures/`
- Concurrent server test with 3 instances searching in parallel

---

### Step 8: Package Structure and Entry Point ✓

**Goal**: Finalize package structure and make server runnable.

**Deliverables**:
- `freeact/agent/tools/pytools/search/hybrid/__init__.py` - exports MCPTOOLS_DIR, GENTOOLS_DIR constants
- `freeact/agent/tools/pytools/search/hybrid/__main__.py` - entry point calling server.main()
- Server runs via `python -m freeact.agent.tools.pytools.search.hybrid` or `uv run -m ...`

**Tests**:
- Integration tests use MCPServerStdio to spawn and communicate with server subprocess
- All tests use constants from `freeact.agent.tools.pytools` for directory names

---

## Phase 4: Integration

### Step 9: System Prompt Updates

**Goal**: Add conditional sections for hybrid search workflow.

**Deliverables**:
- Update `freeact/agent/config/templates/prompts/system.md`
- Add `{tool_discovery_workflow}` placeholder
- Create workflow text for basic mode (current behavior)
- Create workflow text for hybrid mode (search_tools usage)
- Update `Config` class to render appropriate workflow based on server config

**Tests**:
- `tests/unit/agent/config/test_config.py` - verify prompt rendering

---

### Step 10: Configuration Support

**Goal**: Support hybrid search server settings in servers.json.

**Deliverables**:
- Document configuration format in spec (already done)
- Update config loading to pass settings to hybrid server
- Environment variable support for embedding model API keys
- Example servers.json with hybrid search configuration

**Tests**:
- `tests/unit/agent/config/test_servers.py`

---

## Phase 5: Validation

### Step 11: End-to-End Testing

**Goal**: Validate full workflow from config to search results.

**Deliverables**:
- TODO: chceck if this isn't already covered by `tests/integration/tools/pytools/search/hybrid/test_server.py`
- `tests/integration/tools/pytools/search/hybrid/test_e2e.py`
- Test: startup with empty database, full sync
- Test: startup with existing database, incremental sync
- Test: file change triggers re-index
- Test: search returns expected results
- Test: mode switching (bm25/vector/hybrid)

---

### Step 12: Documentation and Cleanup

**Goal**: Finalize documentation and code cleanup.

**Deliverables**:
- Update user documentation in `docs/` with hybrid search usage guide (use mkdocs-formatter skill)
- Update API documentation in `docs/api/` with module reference (use mkdocs-formatter skill)
- Update CLAUDE.md with hybrid search information
- Add docstrings to all public functions/classes
- Run `uv run invoke cc` and fix any issues
- Update spec.md with any changes discovered during implementation
- Remove prototype references from spec (make paths relative to freeact)

---

## Dependencies

```
Step 1 (Database)
    ↓
Step 2 (Extract) ──────┐
    ↓                  │
Step 3 (Search) ◄──────┤
    ↓                  │
Step 4 (Embed) ────────┤
    ↓                  │
Step 5 (Index) ◄───────┘
    ↓
Step 6 (Watch)
    ↓
Step 7 (Server)
    ↓
Step 8 (Package)
    ↓
Step 9 (Prompts) ──┬──► Step 11 (E2E)
    ↓              │        ↓
Step 10 (Config) ──┘   Step 12 (Docs)
```

## Estimated Sessions

| Phase | Steps | Sessions |
|-------|-------|----------|
| Core Infrastructure | 1-3 | 3 |
| Indexing Pipeline | 4-6 | 3 |
| MCP Server | 7-8 | 2 |
| Integration | 9-10 | 2 |
| Validation | 11-12 | 2 |
| **Total** | **12** | **12** |

## Notes

- Steps within the same phase can sometimes be combined if they're small
- Integration tests requiring API keys should be marked with pytest markers for optional execution
- The prototype in `/Users/martin/Development/sandbox/toolsearch/` serves as reference but code should be rewritten to fit freeact patterns
