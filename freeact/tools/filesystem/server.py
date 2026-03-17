import base64
import os
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import BlobResourceContents, EmbeddedResource
from pydantic import Field

from freeact.tools.filesystem.processing import (
    IMAGE_MEDIA_TYPES,
    _guess_media_type,
    _load_media,
    resolve_path,
)
from freeact.tools.filesystem.processing import (
    edit_text_file as _edit_text_file,
)
from freeact.tools.filesystem.processing import (
    read_text_file as _read_text_file,
)
from freeact.tools.filesystem.processing import (
    write_text_file as _write_text_file,
)

mcp = FastMCP("filesystem_mcp", log_level="ERROR")


@mcp.tool(
    name="read_text_file",
    annotations={
        "title": "Read Text File",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    structured_output=False,
)
def read_text_file(
    path: Annotated[str, Field(description="File path to read (absolute or relative to working directory)")],
    offset: Annotated[int | None, Field(description="Line number to start reading from (1-indexed)")] = None,
    limit: Annotated[int | None, Field(description="Maximum number of lines to read")] = None,
) -> str:
    """Read a text file with optional line range."""
    absolute_path = resolve_path(path, os.getcwd())
    resolved = Path(absolute_path)

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not resolved.is_file():
        raise ValueError(f"Not a file: {path}")

    return _read_text_file(absolute_path, offset, limit)


@mcp.tool(
    name="read_media_file",
    annotations={
        "title": "Read Media File",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    structured_output=False,
)
def read_media_file(
    path: Annotated[str, Field(description="File path to read (absolute or relative to working directory)")],
) -> Image | EmbeddedResource:
    """Read a media file (image, audio, video, PDF). The content is attached to the tool result."""
    absolute_path = resolve_path(path, os.getcwd())
    resolved = Path(absolute_path)

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not resolved.is_file():
        raise ValueError(f"Not a file: {path}")

    media_type = _guess_media_type(resolved)
    if media_type is None:
        raise ValueError(f"Not a supported media file: {path}")

    data = _load_media(resolved, media_type)
    if media_type in IMAGE_MEDIA_TYPES:
        fmt = media_type.split("/")[1]
        return Image(data=data, format=fmt)
    return EmbeddedResource(
        type="resource",
        resource=BlobResourceContents(
            uri=resolved.as_uri(),
            mimeType=media_type,
            blob=base64.b64encode(data).decode("ascii"),
        ),
    )


@mcp.tool(
    name="write_text_file",
    annotations={
        "title": "Write Text File",
        "readOnlyHint": False,
        "destructiveHint": True,
    },
)
def write_text_file(
    path: Annotated[str, Field(description="File path to write to")],
    content: Annotated[str, Field(description="Text content to write")],
) -> str:
    """Write text content to a file. Creates parent directories if needed."""
    absolute_path = resolve_path(path, os.getcwd())
    result = _write_text_file(absolute_path, content)
    return f"{result} to {path}"


@mcp.tool(
    name="edit_text_file",
    annotations={
        "title": "Edit Text File",
        "readOnlyHint": False,
        "destructiveHint": True,
    },
)
def edit_text_file(
    path: Annotated[str, Field(description="File path to edit")],
    old_text: Annotated[str, Field(description="Exact text to find and replace (must appear exactly once)")],
    new_text: Annotated[str, Field(description="Text to replace old_text with")],
) -> str:
    """Find and replace text in a file. The old text must appear exactly once in the file."""
    absolute_path = resolve_path(path, os.getcwd())
    result = _edit_text_file(absolute_path, old_text, new_text)
    return f"{path}: {result}"


def main() -> None:
    """Entry point for the Filesystem MCP server."""
    mcp.run(transport="stdio")
