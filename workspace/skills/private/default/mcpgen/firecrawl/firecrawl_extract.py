from __future__ import annotations

from typing import Any, Dict, List, Optional

from ipybox.mcp.run import run_sync
from pydantic import BaseModel, Field

from . import SERVER_PARAMS


class Params(BaseModel):
    urls: List[str]
    """
    List of URLs to extract information from
    """
    prompt: Optional[str] = None
    """
    Prompt for the LLM extraction
    """
    systemPrompt: Optional[str] = None
    """
    System prompt for LLM extraction
    """
    schema_: Optional[Dict[str, Any]] = Field(None, alias="schema")
    """
    JSON schema for structured data extraction
    """
    allowExternalLinks: Optional[bool] = None
    """
    Allow extraction from external links
    """
    enableWebSearch: Optional[bool] = None
    """
    Enable web search for additional context
    """
    includeSubdomains: Optional[bool] = None
    """
    Include subdomains in extraction
    """


def firecrawl_extract(params: Params) -> str:
    """Extract structured information from web pages using LLM. Supports both cloud AI and self-hosted LLM extraction."""
    return run_sync("firecrawl_extract", params.model_dump(exclude_none=True), SERVER_PARAMS)
