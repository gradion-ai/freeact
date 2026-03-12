import json
import os
from typing import Annotated, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from freeact.tools.security import wrap_content

mcp = FastMCP("brave_mcp", log_level="ERROR")

SearchMode = Literal["web", "llm-context"]

_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_LLM_CONTEXT_URL = "https://api.search.brave.com/res/v1/llm/context"
_DEFAULT_COUNT = 5
_TIMEOUT = 30.0


def _get_api_key() -> str:
    """Read BRAVE_API_KEY from env. Raises RuntimeError if not set."""
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        raise RuntimeError("BRAVE_API_KEY environment variable is not set")
    return key


def _request_headers() -> dict[str, str]:
    """Return headers with Accept, Accept-Encoding, X-Subscription-Token."""
    return {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": _get_api_key(),
    }


def _wrap_text(text: str | None) -> str | None:
    """Wrap non-None text with wrap_content(..., "Web Search"). Pass through None."""
    if text is None:
        return None
    return wrap_content(text, "Web Search")


def _parse_web_results(data: dict) -> list[dict]:
    """Extract results from web search response.

    From data["web"]["results"], extracts per result:
    - title: security-wrapped
    - url: NOT wrapped (structural identifier)
    - description: security-wrapped (if present)
    - published: from page_age (if present, NOT wrapped)
    - siteName: from profile.name (if present, security-wrapped)
    """
    web = data.get("web")
    if not web:
        return []
    raw_results = web.get("results", [])
    parsed = []
    for r in raw_results:
        entry: dict = {
            "title": _wrap_text(r.get("title", "")),
            "url": r.get("url", ""),
        }
        description = r.get("description")
        if description is not None:
            entry["description"] = _wrap_text(description)
        page_age = r.get("page_age")
        if page_age is not None:
            entry["published"] = page_age
        profile = r.get("profile")
        if profile and profile.get("name"):
            entry["siteName"] = _wrap_text(profile["name"])
        parsed.append(entry)
    return parsed


def _parse_llm_context_results(data: dict) -> tuple[list[dict], dict]:
    """Extract results from LLM context response.

    From data["grounding"]["generic"], extracts per result:
    - title: security-wrapped
    - url: NOT wrapped
    - snippets: list of individually security-wrapped strings

    Also returns data["sources"] metadata (passed through, not wrapped).
    """
    grounding = data.get("grounding")
    if not grounding:
        return [], {}
    raw_results = grounding.get("generic", [])
    parsed = []
    for r in raw_results:
        entry: dict = {
            "title": _wrap_text(r.get("title", "")),
            "url": r.get("url", ""),
            "snippets": [_wrap_text(s) for s in r.get("snippets", [])],
        }
        parsed.append(entry)
    sources = data.get("sources", {})
    return parsed, sources


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
    match mode:
        case "web":
            url = _WEB_SEARCH_URL
            params: dict[str, str | int] = {"q": query, "count": _DEFAULT_COUNT}
        case "llm-context":
            url = _LLM_CONTEXT_URL
            params = {"q": query}
    headers = _request_headers()

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        took_ms = round(response.elapsed.total_seconds() * 1000)

    output: dict = {
        "query": query,
        "provider": "brave",
        "mode": mode,
        "externalContent": True,
    }

    match mode:
        case "web":
            results = _parse_web_results(data)
            output["results"] = results
        case "llm-context":
            results, sources = _parse_llm_context_results(data)
            output["results"] = results
            output["sources"] = sources

    output["count"] = len(results)
    output["tookMs"] = took_ms

    return json.dumps(output, indent=2)


def main() -> None:
    """Entry point for the Brave Search MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
