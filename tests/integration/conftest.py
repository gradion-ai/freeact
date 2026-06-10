import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import mcpygen
import pytest
import pytest_asyncio
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart

from freeact.tools.pytools import MCPTOOLS_DIR
from tests.integration.mcp_server import STDIO_SERVER_PATH


@pytest.fixture
def mcp_servers() -> dict[str, dict[str, Any]]:
    return {"test": {"command": "python", "args": [str(STDIO_SERVER_PATH)]}}


@pytest_asyncio.fixture
async def mcp_sources_dir(tmp_path: Path) -> Path:
    """Pre-generate MCP sources for PTC testing."""
    await mcpygen.generate_mcp_sources(
        "test",
        {"command": "python", "args": [str(STDIO_SERVER_PATH)]},
        tmp_path / MCPTOOLS_DIR,
    )
    return tmp_path


@pytest.fixture
def stored_path_from_notice() -> Callable[[str, Path], Path]:
    """Extract the stored-file path referenced by a tool-result overflow notice."""

    def _extract(content: str, working_dir: Path) -> Path:
        match = re.search(r"^Full content saved to: (.+)$", content, flags=re.MULTILINE)
        if match is None:
            raise AssertionError("Missing stored-file reference in overflow notice")
        return working_dir / match.group(1)

    return _extract


@pytest.fixture
def collect_tool_return_parts() -> Callable[[list[ModelMessage]], list[ToolReturnPart]]:
    """Collect all ToolReturnParts from a message history."""

    def _collect(messages: list[ModelMessage]) -> list[ToolReturnPart]:
        return [
            part
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]

    return _collect
