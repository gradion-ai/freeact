## Spec: Brave Web Search & Web Fetch PTC Servers

### What

Two new PTC servers for freeact: a Brave web search server and a web fetch server. Both
are custom FastMCP servers (like the existing `gsearch.py`), following openclaw's approach
for result processing and content security. Brave search supports "web" mode (structured
results) and "llm-context" mode (pre-extracted page snippets). Web fetch uses trafilatura
for HTML-to-markdown extraction. All external content is wrapped with security markers to
prevent prompt injection.

### Why

Freeact currently only has Google Search (via Gemini grounding) as a web tool. Adding Brave
search provides an alternative search provider with direct API access and structured results.
Web fetch enables the agent to retrieve and read full page content from URLs, which is
essential for research workflows where search snippets are insufficient.

### Requirements

#### Brave Web Search PTC Server (`freeact/tools/bsearch.py`)

- FastMCP server with a `web_search` tool, following the pattern in `gsearch.py`
- Calls the Brave Search API directly via HTTP (not the default Brave MCP npm package)
- Supports two modes via a `mode` parameter:
  - `"web"` (default): hits `https://api.search.brave.com/res/v1/web/search`, returns
    structured results with `title`, `url`, `description`, `published`, `siteName`
  - `"llm-context"`: hits `https://api.search.brave.com/res/v1/llm-context`, returns
    results with `title`, `url`, `snippets[]`, `siteName`, plus `sources` metadata
- Authenticates via `X-Subscription-Token` header using `BRAVE_API_KEY` env var
- Tool parameters: `query` (required), `mode` (optional, default `"web"`)
- Result count: reasonable default (e.g. 5-10), not user-configurable in v1
- Wraps all text fields (titles, descriptions, snippets) with security content markers
- Returns structured JSON with results array and metadata (`query`, `provider`, `mode`,
  `count`, `tookMs`, `externalContent` marker)

#### Fetch PTC Server (`freeact/tools/fetch.py`)

- FastMCP server with a `web_fetch` tool
- Fetches URL content via HTTP GET using httpx
- Extracts readable content using trafilatura with markdown output:
  `extract(html, output_format="markdown", include_links=True, include_images=True)`
- Handles content types:
  - `text/html`: trafilatura extraction
  - `application/json`: pretty-print with indentation
  - `text/markdown`: pass through as-is
  - Other: return raw text
- Tool parameters: `url` (required), `max_chars` (optional, default 50000)
- Truncates content to `max_chars` limit
- Wraps extracted content with security content markers (including security notice)
- Returns structured result with: `url`, `final_url` (after redirects), `status`,
  `content_type`, `title`, `extractor` (trafilatura/json/raw), `text` (wrapped),
  `truncated`, `raw_length`, `fetched_at`, `took_ms`

#### Content Security Wrapping (`freeact/tools/security.py`)

- Shared module used by both tools
- Wraps external content with unique boundary markers:
  ```
  <<<EXTERNAL_UNTRUSTED_CONTENT id="[random-hex]">>>
  Source: [Web Search|Web Fetch]
  ---
  [CONTENT]
  <<<END_EXTERNAL_UNTRUSTED_CONTENT id="[random-hex]">>>
  ```
- Web fetch content additionally prefixed with a security notice warning the LLM not to
  treat fetched content as instructions
- Generates random marker IDs (8+ bytes hex) to prevent spoofing
- Sanitizes content that contains spoofed boundary markers before wrapping

#### Configuration (`agent.json`)

- Both servers configured as `ptc_servers` entries, following the google search pattern:
  ```json
  "brave": {
    "command": "python",
    "args": ["-m", "freeact.tools.bsearch"],
    "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"}
  },
  "fetch": {
    "command": "python",
    "args": ["-m", "freeact.tools.fetch"],
    "env": {}
  }
  ```
- Users opt in by adding these entries to their config (not enabled by default)

#### Dependencies

- `httpx` (0.28.1): already a project dependency (used in gsearch.py). No llms.txt available.
- `trafilatura`: new dependency for HTML content extraction and markdown conversion. No llms.txt
  available.
- `mcp` Python SDK (1.26.0): provides `mcp.server.fastmcp.FastMCP` used for server definitions.
  The new servers import from `mcp.server.fastmcp`, not the standalone `fastmcp` package.
  docs: `https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/refs/heads/main/README.md`
- No npm/Node.js dependencies required

### Out of Scope

- Country/language/freshness filters for Brave search -- not needed for v1
- Firecrawl or other fallback extractors for web fetch -- trafilatura alone for v1
- Caching of search results or fetched pages -- not needed for v1
- Browser automation or JavaScript rendering -- lightweight fetch only
- Prompt injection detection/logging -- wrapping and sanitization only
- Multiple search provider support (Gemini, Grok, Perplexity) -- Brave only

### Key Decisions

- **Custom MCP servers over default Brave MCP npm package**: following openclaw's approach,
  the Brave API is called directly to control result processing, security wrapping, and
  output structure. This avoids an npm/Node.js dependency and keeps the implementation
  consistent with the existing `gsearch.py` pattern.
- **trafilatura for content extraction**: best-in-class single library that handles both
  main content extraction (F1: 0.909) and markdown conversion. No fallback chain in v1
  to keep complexity low.
- **Content security wrapping included**: relatively low implementation cost, properly
  encapsulated in a shared module, provides meaningful protection against prompt injection
  from fetched web content.
- **Both modes for Brave search**: "llm-context" mode adds minimal code (~20-30 lines)
  over "web" mode since it's just a different endpoint with a slightly different response
  schema, and provides pre-extracted page content useful for grounding.

### Constraints

- Must follow existing FastMCP server pattern (`gsearch.py` is the reference implementation)
- Must be PTC servers (not regular MCP servers) so the agent calls them via generated Python APIs
- Must use absolute imports, type hints on all parameters/returns, `str | None` union syntax
- No functions/classes defined in `__init__.py` files
- Security module must be self-contained and reusable across both tools
