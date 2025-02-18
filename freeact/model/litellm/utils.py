import re
from typing import Any


def tool_name(tool: dict[str, Any]) -> str:
    """Extracts the tool name from a [tool definition](https://platform.openai.com/docs/guides/function-calling#defining-functions)."""
    return tool["function"]["name"]


def sanitize_tool_name(tool_name: str) -> str:
    """Sanitizes a tool name by replacing non-alphanumeric characters with underscores."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", tool_name)


def code_blocks(text: str, pattern: str = r"```python\n(.*?)```") -> list[str]:
    """Finds all blocks matching `pattern` in `text`."""
    blocks = re.findall(pattern, text, re.DOTALL)
    return [block.strip() for block in blocks]


def code_block(text: str, index: int, **kwargs) -> str | None:
    """Finds the `index`-th block matching `pattern` in `text`."""
    blocks = code_blocks(text, **kwargs)
    return blocks[index] if blocks else None
