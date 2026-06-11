import json
from dataclasses import asdict
from pathlib import Path

from ipybox.utils import arun
from pydantic_ai.tools import ToolDefinition

IPYBOX_TOOL_PREFIX = "ipybox"
IPYBOX_TOOL_DEFS_PATH = Path(__file__).parent / "ipybox.json"
SUBAGENT_TOOL_DEFS_PATH = Path(__file__).parent / "subagent.json"


def load_tool_definitions(path: Path) -> list[ToolDefinition]:
    """Load tool definitions from a JSON file.

    Args:
        path: Path to JSON file containing serialized tool definitions.

    Returns:
        List of deserialized tool definitions.
    """
    data = json.loads(path.read_text())
    return [ToolDefinition(**item) for item in data]


def save_tool_definitions(tool_defs: list[ToolDefinition], path: Path) -> None:
    """Persist tool definitions to a JSON file.

    Args:
        tool_defs: Tool definitions to serialize.
        path: Destination file path.
    """
    data = [asdict(tool_def) for tool_def in tool_defs]
    path.write_text(json.dumps(data, indent=2))


async def load_ipybox_tool_definitions() -> list[ToolDefinition]:
    """Load cached ipybox tool definitions from the bundled JSON file."""
    return await arun(load_tool_definitions, IPYBOX_TOOL_DEFS_PATH)


async def load_subagent_task_tool_definitions() -> list[ToolDefinition]:
    """Load cached subagent task tool definitions from the bundled JSON file."""
    return await arun(load_tool_definitions, SUBAGENT_TOOL_DEFS_PATH)
