# Phase 3: Fetch PTC Server

## Context

We're building two new PTC servers for freeact (Brave web search and web fetch). Phase 1 (content security module `freeact/tools/security.py`) and Phase 2 (Brave search server `freeact/tools/bsearch.py`) are complete. Phase 3 adds the fetch PTC server that retrieves and extracts readable content from URLs, with content-type-aware extraction and security wrapping.

Spec: `docs/internal/features/active/web-tools/feat-spec.md`
Plan: `docs/internal/features/active/web-tools/feat-plan.md`

## Files to Create

| File | Purpose |
|------|---------|
| `freeact/tools/fetch.py` | Fetch FastMCP PTC server |
| `tests/unit/tools/test_fetch.py` | Unit tests |

Modify: `pyproject.toml` -- add `trafilatura` to `[project] dependencies` via `uv add trafilatura`.

No other existing files modified. Users opt in by adding the server entry to their `agent.json` manually.

## Public API

```python
@mcp.tool(
    name="web_fetch",
    annotations={
        "title": "Web Fetch",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    structured_output=False,
)
async def web_fetch(
    url: Annotated[str, Field(description="URL to fetch content from")],
    max_chars: Annotated[
        int,
        Field(description="Maximum characters to return (content is truncated beyond this limit)"),
    ] = 50000,
) -> str:
    """Fetch and extract readable content from a URL.

    Retrieves the URL via HTTP GET, extracts readable content based on
    content type (HTML via trafilatura, JSON via pretty-print, markdown
    pass-through, other as raw text), truncates to max_chars, and wraps
    with security markers.
    """
```

Follows the `bsearch.py` pattern: `FastMCP` server, `@mcp.tool()` with annotations, `structured_output=False`, returns JSON string.

## Internal Implementation

### Module structure

```python
import datetime
import json
from typing import Annotated

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from trafilatura import extract
from trafilatura.metadata import extract_metadata

from freeact.tools.security import wrap_fetch_content

mcp = FastMCP("fetch_mcp", log_level="ERROR")

_DEFAULT_MAX_CHARS = 50000
_TIMEOUT = 30.0
_USER_AGENT = "freeact-fetch/1.0"
```

### Private functions

**`_parse_content_type(content_type_header: str) -> str`**
- `content_type_header.split(";")[0].strip().lower()`
- E.g. `"text/html; charset=utf-8"` -> `"text/html"`

**`_extract_content(response_text: str, content_type: str) -> tuple[str, str | None, str]`**
- Returns `(text, title, extractor)`
- Dispatch by content type:
  - `text/html`: `trafilatura.extract(response_text, output_format="markdown", include_links=True, include_images=True)`. If returns `None`, fall back to raw text with `extractor="raw"`. Title via `trafilatura.metadata.extract_metadata(response_text)` -> `.title` attribute.
  - `application/json`: `json.dumps(json.loads(response_text), indent=2)`. If JSON parse fails, fall back to raw. `extractor="json"`. Title is `None`.
  - `text/markdown`: pass-through. `extractor="raw"`. Title is `None`.
  - Other: raw `response_text`. `extractor="raw"`. Title is `None`.

**`_truncate(text: str, max_chars: int) -> tuple[str, bool]`**
- If `len(text) > max_chars`: return `(text[:max_chars], True)`
- Otherwise: return `(text, False)`

### Tool function flow

1. `async with httpx.AsyncClient(follow_redirects=True) as client:`
2. `response = await client.get(url, timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT})`
3. `response.raise_for_status()`
4. Parse content type, get `response.text`, `str(response.url)` for final URL
5. `took_ms = round(response.elapsed.total_seconds() * 1000)`
6. `_extract_content(response_text, content_type)` -> `(text, title, extractor)`
7. `raw_length = len(text)`, then `_truncate(text, max_chars)`
8. `wrap_fetch_content(text)` from `freeact.tools.security`
9. `fetched_at = datetime.datetime.now(datetime.UTC).isoformat()`
10. Assemble output dict, return `json.dumps(output, indent=2)`

### Entry point

```python
def main() -> None:
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

## JSON Output Structure

```json
{
  "url": "https://example.com/page",
  "finalUrl": "https://example.com/page",
  "status": 200,
  "contentType": "text/html",
  "title": "Page Title",
  "extractor": "trafilatura",
  "text": "<<<EXTERNAL_UNTRUSTED_CONTENT id=\"...\">>>\n[NOTE: ...]\nSource: Web Fetch\n---\n...\n<<<END_EXTERNAL_UNTRUSTED_CONTENT id=\"...\">>>",
  "truncated": false,
  "rawLength": 12345,
  "fetchedAt": "2026-03-12T10:30:00+00:00",
  "tookMs": 450,
  "externalContent": true
}
```

CamelCase JSON keys for consistency with `bsearch.py` output (`tookMs`, `externalContent`).

## Test Plan

File: `tests/unit/tools/test_fetch.py`

Mock strategy:
- httpx: same `AsyncMock`/`MagicMock` pattern as `test_bsearch.py`, extended with `mock_response.text`, `mock_response.url`, `mock_response.headers`
- trafilatura: `monkeypatch.setattr("freeact.tools.fetch.extract", ...)` and `monkeypatch.setattr("freeact.tools.fetch.extract_metadata", ...)`
- security: `monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)`

### `class TestParseContentType:`
1. `test_extracts_mime_type` -- `"text/html; charset=utf-8"` -> `"text/html"`
2. `test_no_params` -- `"application/json"` -> `"application/json"`
3. `test_empty_string` -- `""` -> `""`
4. `test_uppercased` -- `"TEXT/HTML"` -> `"text/html"`

### `class TestExtractContent:`
5. `test_html_uses_trafilatura` -- mock extract returning markdown, verify extractor is `"trafilatura"`
6. `test_html_extracts_title` -- mock extract_metadata returning object with title
7. `test_html_extraction_failure_falls_back_to_raw` -- mock extract returning None, verify `extractor="raw"`
8. `test_json_pretty_prints` -- valid JSON, verify indented output, `extractor="json"`
9. `test_json_parse_failure_falls_back_to_raw` -- invalid JSON, `extractor="raw"`
10. `test_markdown_passes_through` -- `text/markdown`, content unchanged, `extractor="raw"`
11. `test_other_returns_raw` -- `text/plain`, content as-is, `extractor="raw"`
12. `test_html_title_none_when_metadata_fails` -- mock extract_metadata returning None

### `class TestTruncate:`
13. `test_no_truncation_needed` -- short text, `(text, False)`
14. `test_truncates_at_limit` -- long text, `(text[:limit], True)`
15. `test_exact_length_not_truncated` -- exact limit, `(text, False)`

### `class TestFetchTool:`

Helper `_mock_httpx(self, monkeypatch, response_text, content_type, status_code, final_url)` following `test_bsearch.py::TestWebSearchTool._mock_httpx` pattern but adapted for fetch (response.text, response.url, response.headers, `AsyncClient(**kwargs)` lambda).

16. `test_fetches_url_with_get` -- verify mock_get called with the URL
17. `test_follows_redirects` -- verify AsyncClient created with `follow_redirects=True`
18. `test_returns_json_with_all_fields` -- validate full output structure
19. `test_html_content_extracted_as_markdown` -- mock trafilatura, verify `extractor="trafilatura"`
20. `test_json_content_pretty_printed` -- JSON response, verify `extractor="json"`
21. `test_text_content_passed_through` -- `text/plain`, verify `extractor="raw"`
22. `test_content_truncated_at_max_chars` -- content > max_chars, verify `truncated: true` and `rawLength`
23. `test_content_security_wrapped` -- verify `<<<EXTERNAL_UNTRUSTED_CONTENT` and security notice in text
24. `test_default_max_chars_is_50000` -- no max_chars arg, no truncation for content < 50000
25. `test_final_url_from_response` -- different mock response.url, verify `finalUrl`
26. `test_status_code_in_output` -- verify `status` field
27. `test_took_ms_in_output` -- verify computed from `response.elapsed`
28. `test_http_error_propagates` -- mock 404, verify `httpx.HTTPStatusError` raised
29. `test_external_content_flag` -- verify `externalContent: true`

## Reused Code

| What | Where |
|------|-------|
| `wrap_fetch_content(content)` | `freeact/tools/security.py:50` |
| FastMCP server pattern | `freeact/tools/bsearch.py` |
| httpx mock pattern | `tests/unit/tools/test_bsearch.py:170` |
| Test class organization | `tests/unit/tools/test_bsearch.py` |

## Implementation Order (TDD)

1. Add dependency: `uv add trafilatura`
2. Write all tests in `tests/unit/tools/test_fetch.py` (fail with `ModuleNotFoundError`)
3. Create `freeact/tools/fetch.py` with stubs (correct signatures, return `""`)
4. Implement `_parse_content_type`
5. Implement `_truncate`
6. Implement `_extract_content` (content type dispatch with trafilatura, json, raw branches)
7. Implement `web_fetch` tool function (httpx call, extraction, truncation, wrapping, JSON assembly)
8. Implement `main()` entry point
9. Run: `uv run pytest -xvs tests/unit/tools/test_fetch.py`
10. `git add` new files, run: `uv run invoke cc`
11. Run full unit suite: `uv run invoke ut`

## Verification

1. `uv run pytest -xvs tests/unit/tools/test_fetch.py` -- all 29 tests pass
2. `uv run invoke cc` -- ruff format + mypy pass
3. `uv run invoke ut` -- no regressions
4. End-to-end via `freeact-interaction` skill:
   - `uv run freeact init` if `.freeact/` missing
   - Add fetch entry to `.freeact/agent.json` `ptc_servers`:
     ```json
     "fetch": {
       "command": "python",
       "args": ["-m", "freeact.tools.fetch"],
       "env": {}
     }
     ```
   - Send prompt asking agent to fetch a URL
   - Approve tool executions, verify extracted content in response
