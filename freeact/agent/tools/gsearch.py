import argparse
from typing import Annotated

import httpx
from google import genai
from google.genai import types
from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("google_mcp", log_level="ERROR")

_thinking_level: str = "low"


async def _get_redirect_target(url: str) -> str:
    """Follow redirects and return the final URL."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.head(url)
        return str(response.url)


@mcp.tool(
    name="web_search",
    annotations={
        "title": "Web Search",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def web_search(
    query: Annotated[
        str,
        Field(description="Natural language question or topic"),
    ],
) -> str:
    """Web search using Google Search grounding with Gemini-generated answer.

    Uses Gemini with Google Search grounding to answer queries. Returns a
    synthesized answer (not raw search results) followed by numbered source URLs.
    Query should be natural language, e.g., "Who is the author of X?".
    """
    client = genai.Client()

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(thinking_level=_thinking_level),
    )

    response = await client.aio.models.generate_content(
        model="gemini-3-flash-preview",
        contents=query,
        config=config,
    )

    result_parts: list[str] = [response.text or ""]

    # Extract grounding chunks and resolve redirect URLs
    if response.candidates and response.candidates[0].grounding_metadata:
        metadata = response.candidates[0].grounding_metadata
        if metadata.grounding_chunks:
            references: list[str] = []
            for i, chunk in enumerate(metadata.grounding_chunks):
                if chunk.web:
                    target_url = await _get_redirect_target(chunk.web.uri)
                    references.append(f"[{i + 1}]: {target_url}")
            if references:
                result_parts.append("")
                result_parts.extend(references)

    return "\n".join(result_parts)


def main() -> None:
    """Entry point for the Google Search MCP server."""
    global _thinking_level
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--thinking-level",
        default="low",
        choices=["minimal", "low", "medium", "high"],
        help="Thinking level for the model",
    )
    args = parser.parse_args()
    _thinking_level = args.thinking_level
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
