import datetime
import json
from typing import Annotated

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from trafilatura import extract, html2txt
from trafilatura.metadata import extract_metadata

from freeact.tools.security import wrap_fetch_content

mcp = FastMCP("fetch_mcp", log_level="ERROR")

_DEFAULT_MAX_CHARS = 50000
_TIMEOUT = 30.0
_USER_AGENT = "freeact-fetch/1.0"
_EXTRACTION_RATIO_THRESHOLD = 0.5


def _parse_content_type(content_type_header: str) -> str:
    """Extract MIME type from Content-Type header, stripping parameters."""
    return content_type_header.split(";")[0].strip().lower()


def _extract_html(response_text: str) -> tuple[str, str | None, str]:
    """Extract readable content from HTML using trafilatura.

    Uses `trafilatura.extract` for rich markdown output. Falls back to
    `trafilatura.html2txt` when extraction returns None or captures less
    than half the page's plain-text content.
    """
    meta = extract_metadata(response_text)
    title = meta.title if meta is not None else None
    plain_text = html2txt(response_text)
    plain_len = len(plain_text) if plain_text else 0

    extracted = extract(response_text, output_format="markdown", include_links=True, include_images=True)
    if extracted is not None and (plain_len == 0 or len(extracted) / plain_len >= _EXTRACTION_RATIO_THRESHOLD):
        return extracted, title, "trafilatura"

    if plain_text:
        return plain_text, title, "trafilatura-plain"

    return response_text, title, "raw"


def _extract_content(response_text: str, content_type: str) -> tuple[str, str | None, str]:
    """Extract readable content based on content type.

    Returns a tuple of (text, title, extractor) where extractor indicates
    the method used: "trafilatura", "trafilatura-plain", "json", or "raw".
    """
    if content_type == "text/html":
        return _extract_html(response_text)

    if content_type == "application/json":
        try:
            parsed = json.loads(response_text)
            return json.dumps(parsed, indent=2), None, "json"
        except (json.JSONDecodeError, ValueError):
            return response_text, None, "raw"

    return response_text, None, "raw"


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate text to max_chars if needed. Returns (text, was_truncated)."""
    if len(text) > max_chars:
        return text[:max_chars], True
    return text, False


@mcp.tool(
    name="fetch",
    annotations={
        "title": "Web Fetch",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    structured_output=False,
)
async def fetch(
    url: Annotated[str, Field(description="URL to fetch content from")],
    max_chars: Annotated[
        int,
        Field(description="Maximum characters to return (content is truncated beyond this limit)"),
    ] = _DEFAULT_MAX_CHARS,
) -> str:
    """Fetch and extract readable content from a URL.

    Retrieves the URL via HTTP GET, extracts readable content based on
    content type (HTML via trafilatura, JSON via pretty-print, markdown
    pass-through, other as raw text), truncates to max_chars, and wraps
    with security markers.
    """
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()

        response_text = response.text
        final_url = str(response.url)
        status_code = response.status_code
        content_type_header = response.headers.get("content-type", "")
        took_ms = round(response.elapsed.total_seconds() * 1000)

    content_type = _parse_content_type(content_type_header)
    text, title, extractor = _extract_content(response_text, content_type)
    raw_length = len(text)
    text, truncated = _truncate(text, max_chars)
    text = wrap_fetch_content(text)
    fetched_at = datetime.datetime.now(datetime.UTC).isoformat()

    output: dict = {
        "url": url,
        "finalUrl": final_url,
        "status": status_code,
        "contentType": content_type,
        "title": title,
        "extractor": extractor,
        "text": text,
        "truncated": truncated,
        "rawLength": raw_length,
        "fetchedAt": fetched_at,
        "tookMs": took_ms,
        "externalContent": True,
    }

    return json.dumps(output, indent=2)


def main() -> None:
    """Entry point for the Fetch MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
