# Plan: Brave Web Search & Fetch PTC Servers

Spec: docs/internal/features/active/web-tools/SPEC.md

## Phase 1: Content Security Module

**Goal:** Provide a shared, reusable module for wrapping external content with security boundary markers to prevent prompt injection.

**Requirements from spec:**
- Shared module used by both tools (`freeact/tools/security.py`)
- Wraps external content with unique boundary markers (source label + random hex ID)
- Web fetch content additionally prefixed with a security notice
- Generates random marker IDs (8+ bytes hex) to prevent spoofing
- Sanitizes content that contains spoofed boundary markers before wrapping

**Depends on:** --

**Success criteria:**
- [x] Security module wraps content with correct boundary format and unique IDs
- [x] Spoofed markers in content are sanitized before wrapping
- [x] Web fetch variant includes security notice prefix

## Phase 2: Brave Web Search Server

**Goal:** Add a Brave Search PTC server that queries the Brave API in both "web" and "llm-context" modes, returning security-wrapped structured results.

**Requirements from spec:**
- FastMCP server with a `web_search` tool, following the pattern in `gsearch.py`
- Calls Brave Search API directly via HTTP (not the default Brave MCP npm package)
- `"web"` mode (default): structured results with `title`, `url`, `description`, `published`, `siteName`
- `"llm-context"` mode: results with `title`, `url`, `snippets[]`, `siteName`, plus `sources` metadata
- Authenticates via `X-Subscription-Token` header using `BRAVE_API_KEY` env var
- Tool parameters: `query` (required), `mode` (optional, default `"web"`)
- Reasonable default result count (5-10), not user-configurable in v1
- Wraps all text fields with security content markers
- Returns structured JSON with results array and metadata
- Config entry in `agent.json` under `ptc_servers`

**Depends on:** Phase 1

**Success criteria:**
- [x] `web_search` tool returns structured results from Brave API in "web" mode
- [x] `web_search` tool returns structured results in "llm-context" mode
- [x] All text fields in results are security-wrapped
- [x] Server is configurable as a PTC server entry in `agent.json`
- [x] End-to-end test via freeact-interaction skill: agent performs a Brave search through the terminal UI and returns results
- [x] Documentation updated

## Phase 3: Fetch Server

**Goal:** Add a fetch PTC server that retrieves and extracts readable content from URLs, with content-type-aware extraction and security wrapping.

**Requirements from spec:**
- FastMCP server with a `fetch` tool (`freeact/tools/fetch.py`)
- Fetches URL content via HTTP GET using httpx
- Extracts readable content using trafilatura with markdown output
- Content type handling: HTML (trafilatura), JSON (pretty-print), markdown (pass-through), other (raw text)
- Tool parameters: `url` (required), `max_chars` (optional, default 50000)
- Truncates content to `max_chars` limit
- Wraps extracted content with security content markers (including security notice)
- Returns structured result with: `url`, `final_url`, `status`, `content_type`, `title`, `extractor`, `text`, `truncated`, `raw_length`, `fetched_at`, `took_ms`
- `trafilatura` added as new dependency
- Config entry in `agent.json` under `ptc_servers`

**Depends on:** Phase 1

**Success criteria:**
- [x] `fetch` tool retrieves and extracts HTML pages as markdown via trafilatura
- [x] JSON, markdown, and other content types are handled correctly
- [x] Content is truncated at `max_chars` and security-wrapped
- [x] Server is configurable as a PTC server entry in `agent.json`
- [x] End-to-end test via freeact-interaction skill: agent fetches a URL through the terminal UI and returns extracted content
- [x] Documentation updated

## Coverage

All requirements from SPEC.md are assigned to a phase.
