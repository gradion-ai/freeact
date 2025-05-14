from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from ipybox.mcp.run import run_sync
from pydantic import BaseModel, Field

from . import SERVER_PARAMS


class Format(Enum):
    markdown = "markdown"
    html = "html"
    rawHtml = "rawHtml"
    screenshot = "screenshot"
    links = "links"
    screenshot_fullPage = "screenshot@fullPage"
    extract = "extract"


class Type(Enum):
    wait = "wait"
    click = "click"
    screenshot = "screenshot"
    write = "write"
    press = "press"
    scroll = "scroll"
    scrape = "scrape"
    executeJavascript = "executeJavascript"


class Direction(Enum):
    up = "up"
    down = "down"


class Action(BaseModel):
    type: Type
    """
    Type of action to perform
    """
    selector: Optional[str] = None
    """
    CSS selector for the target element
    """
    milliseconds: Optional[float] = None
    """
    Time to wait in milliseconds (for wait action)
    """
    text: Optional[str] = None
    """
    Text to write (for write action)
    """
    key: Optional[str] = None
    """
    Key to press (for press action)
    """
    direction: Optional[Direction] = None
    """
    Scroll direction
    """
    script: Optional[str] = None
    """
    JavaScript code to execute
    """
    fullPage: Optional[bool] = None
    """
    Take full page screenshot
    """


class Extract(BaseModel):
    schema_: Optional[Dict[str, Any]] = Field(None, alias="schema")
    """
    Schema for structured data extraction
    """
    systemPrompt: Optional[str] = None
    """
    System prompt for LLM extraction
    """
    prompt: Optional[str] = None
    """
    User prompt for LLM extraction
    """


class Location(BaseModel):
    country: Optional[str] = None
    """
    Country code for geolocation
    """
    languages: Optional[List[str]] = None
    """
    Language codes for content
    """


class Params(BaseModel):
    url: str
    """
    The URL to scrape
    """
    formats: Optional[List[Format]] = ["markdown"]  # type: ignore
    """
    Content formats to extract (default: ['markdown'])
    """
    onlyMainContent: Optional[bool] = None
    """
    Extract only the main content, filtering out navigation, footers, etc.
    """
    includeTags: Optional[List[str]] = None
    """
    HTML tags to specifically include in extraction
    """
    excludeTags: Optional[List[str]] = None
    """
    HTML tags to exclude from extraction
    """
    waitFor: Optional[float] = None
    """
    Time in milliseconds to wait for dynamic content to load
    """
    timeout: Optional[float] = None
    """
    Maximum time in milliseconds to wait for the page to load
    """
    actions: Optional[List[Action]] = None
    """
    List of actions to perform before scraping
    """
    extract: Optional[Extract] = None
    """
    Configuration for structured data extraction
    """
    mobile: Optional[bool] = None
    """
    Use mobile viewport
    """
    skipTlsVerification: Optional[bool] = None
    """
    Skip TLS certificate verification
    """
    removeBase64Images: Optional[bool] = None
    """
    Remove base64 encoded images from output
    """
    location: Optional[Location] = None
    """
    Location settings for scraping
    """


def firecrawl_scrape(params: Params) -> str:
    """Scrape a single webpage with advanced options for content extraction. Supports various formats including markdown, HTML, and screenshots. Can execute custom actions like clicking or scrolling before scraping."""
    return run_sync("firecrawl_scrape", params.model_dump(exclude_none=True), SERVER_PARAMS)
