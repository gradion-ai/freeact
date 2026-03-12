# Phase 2: Brave Web Search PTC Server

## Context

We're building two new PTC servers for freeact (Brave web search and web fetch). Phase 1 (content security module in `freeact/tools/security.py`) is complete. Phase 2 adds the Brave Search PTC server that queries the Brave API in both "web" and "llm-context" modes, returning security-wrapped structured results.

Spec: `docs/internal/features/active/web-tools/feat-spec.md`
Plan: `docs/internal/features/active/web-tools/feat-plan.md`

## Files to Create

| File | Purpose |
|------|---------|
| `freeact/tools/bsearch.py` | Brave Search FastMCP PTC server |
| `tests/unit/tools/test_bsearch.py` | Unit tests |

No existing files modified. Users opt in by adding the server to their `agent.json` manually (not enabled by default).

## Public API

```python
# freeact/tools/bsearch.py
from typing import Annotated, Literal

SearchMode = Literal["web", "llm-context"]

@mcp.tool(
    name="web_search",
    annotations={
        "title": "Web Search",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    structured_output=False,
)
async def web_search(
    query: Annotated[str, Field(description="Natural language question or topic")],
    mode: Annotated[
        SearchMode,
        Field(description="Search mode: 'web' for structured results, 'llm-context' for pre-extracted snippets"),
    ] = "web",
) -> str:
    """Web search using Brave Search API.

    Returns structured JSON with search results. In 'web' mode, returns
    titles, URLs, and descriptions. In 'llm-context' mode, returns titles,
    URLs, and pre-extracted page snippets for language model grounding.
    """
```

Follows `gsearch.py` pattern: `FastMCP` server, `@mcp.tool()` decorator with annotations, `structured_output=False`, returns JSON string.

## Internal Implementation

**Constants:**
```python
_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_LLM_CONTEXT_URL = "https://api.search.brave.com/res/v1/llm/context"
_DEFAULT_COUNT = 5
_TIMEOUT = 30.0
```

Note: the spec had `/res/v1/llm-context` but the correct Brave API endpoint is `/res/v1/llm/context`.

**Private functions:**

```python
def _get_api_key() -> str:
    """Read BRAVE_API_KEY from env. Raises RuntimeError if not set."""

def _request_headers() -> dict[str, str]:
    """Return headers with Accept, Accept-Encoding, X-Subscription-Token."""

def _wrap_text(text: str | None) -> str | None:
    """Wrap non-None text with wrap_content(..., "Web Search"). Pass through None."""

def _parse_web_results(data: dict) -> list[dict]:
    """Extract results from web search response.

    From data["web"]["results"], extracts per result:
    - title: security-wrapped
    - url: NOT wrapped (structural identifier)
    - description: security-wrapped (if present)
    - published: from page_age (if present, NOT wrapped -- Brave-computed date)
    - siteName: from profile.name (if present, security-wrapped)
    """

def _parse_llm_context_results(data: dict) -> tuple[list[dict], dict]:
    """Extract results from LLM context response.

    From data["grounding"]["generic"], extracts per result:
    - title: security-wrapped
    - url: NOT wrapped
    - snippets: list of individually security-wrapped strings

    Also returns data["sources"] metadata (passed through, not wrapped).
    """
```

**Security wrapping strategy:**
- Wrapped: `title`, `description`, `snippets[]`, `siteName` (from external web pages, could contain prompt injection)
- NOT wrapped: `url`, `published`, `sources` metadata (structural/Brave-computed data)

**`web_search` tool flow:**
1. `match mode` to select URL and params (`q`, `count`)
2. `httpx.AsyncClient().get(...)` with auth headers, `raise_for_status()`
3. `match mode` to select parser (`_parse_web_results` or `_parse_llm_context_results`)
4. Assemble output dict with metadata (`query`, `provider`, `mode`, `count`, `tookMs`, `externalContent`)
5. `json.dumps(output, indent=2)`

**Error handling:** Exceptions propagate naturally (matches `gsearch.py` pattern). The MCP framework catches and returns them as tool errors.

**Entry point:**
```python
def main() -> None:
    """Entry point for the Brave Search MCP server."""
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

No `argparse` needed (unlike `gsearch.py` which has `--thinking-level`). No CLI args in v1.

## JSON Output Structure

**Web mode:**
```json
{
  "query": "example query",
  "provider": "brave",
  "mode": "web",
  "count": 3,
  "tookMs": 450,
  "externalContent": true,
  "results": [
    {
      "title": "<<<EXTERNAL_UNTRUSTED_CONTENT id=\"...\">>>...",
      "url": "https://example.com",
      "description": "<<<EXTERNAL_UNTRUSTED_CONTENT id=\"...\">>>...",
      "published": "2 days ago",
      "siteName": "<<<EXTERNAL_UNTRUSTED_CONTENT id=\"...\">>>..."
    }
  ]
}
```

**LLM-context mode:** same structure plus `snippets` array per result and top-level `sources` dict.

## Configuration (user-managed, not in code)

Users add to their `agent.json`:
```json
{
  "ptc_servers": {
    "brave": {
      "command": "python",
      "args": ["-m", "freeact.tools.bsearch"],
      "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"}
    }
  }
}
```

## Test Plan

File: `tests/unit/tools/test_bsearch.py`

Mock strategy: `monkeypatch.setattr` on `httpx.AsyncClient` to return mock responses. `monkeypatch.setattr("freeact.tools.security.secrets.token_hex", ...)` for deterministic marker IDs where needed.

### `class TestGetApiKey:`
1. `test_returns_key_from_env` -- monkeypatch.setenv, assert returned
2. `test_raises_when_not_set` -- monkeypatch.delenv, assert RuntimeError

### `class TestRequestHeaders:`
3. `test_includes_subscription_token` -- check X-Subscription-Token
4. `test_includes_accept_json` -- check Accept header

### `class TestWrapText:`
5. `test_wraps_non_none_text` -- returns wrapped string
6. `test_returns_none_for_none` -- returns None

### `class TestParseWebResults:`
7. `test_extracts_title_url_description` -- basic fields present
8. `test_wraps_title` -- title is security-wrapped
9. `test_wraps_description` -- description is security-wrapped
10. `test_does_not_wrap_url` -- url is plain string
11. `test_includes_published` -- page_age mapped to published
12. `test_includes_site_name` -- profile.name mapped and wrapped
13. `test_missing_optional_fields` -- absent fields omitted from result
14. `test_empty_results` -- empty results list returns empty
15. `test_missing_web_key` -- data without "web" returns empty

### `class TestParseLlmContextResults:`
16. `test_extracts_title_url_snippets` -- basic fields
17. `test_wraps_title` -- title is security-wrapped
18. `test_wraps_each_snippet` -- each snippet individually wrapped
19. `test_does_not_wrap_url` -- url is plain
20. `test_empty_grounding` -- empty list returns empty
21. `test_missing_grounding_key` -- returns empty
22. `test_returns_sources` -- sources dict passed through

### `class TestWebSearchTool:`
23. `test_web_mode_calls_correct_url` -- mock httpx, verify web URL
24. `test_llm_context_mode_calls_correct_url` -- verify llm/context URL
25. `test_passes_query_param` -- verify q=query
26. `test_passes_count_param` -- verify count param
27. `test_passes_auth_header` -- verify X-Subscription-Token
28. `test_web_mode_returns_json_with_results` -- full output structure
29. `test_llm_context_mode_returns_json_with_results_and_sources`
30. `test_output_metadata_fields` -- query, provider, mode, count, tookMs, externalContent
31. `test_default_mode_is_web` -- no mode arg uses web endpoint
32. `test_http_error_propagates` -- mock 401, assert HTTPStatusError
33. `test_missing_api_key_raises` -- no BRAVE_API_KEY, assert RuntimeError

## Implementation Order (TDD)

1. Write all tests in `tests/unit/tools/test_bsearch.py` (fail with `ModuleNotFoundError`)
2. Create `freeact/tools/bsearch.py` with stubs (correct signatures, return `""`)
3. Implement `_get_api_key` and `_request_headers`
4. Implement `_wrap_text`
5. Implement `_parse_web_results`
6. Implement `_parse_llm_context_results`
7. Implement `web_search` tool function (httpx call, parsing, JSON assembly)
8. Implement `main()` entry point
9. `git add` new files, run: `uv run invoke cc`
10. `uv run invoke ut` -- no regressions

## Reused Code

| What | Where |
|------|-------|
| `wrap_content(content, "Web Search")` | `freeact/tools/security.py:33` |
| FastMCP server pattern | `freeact/tools/gsearch.py` |
| Test patterns (monkeypatch, class org) | `tests/unit/tools/test_security.py` |

## Verification

1. `uv run pytest -xvs tests/unit/tools/test_bsearch.py` -- all 33 tests pass
2. `uv run invoke cc` -- ruff format + mypy pass
3. `uv run invoke ut` -- no regressions in full unit suite
4. End-to-end test via `freeact-interaction` skill: configure brave PTC server, agent performs a Brave search through terminal UI
