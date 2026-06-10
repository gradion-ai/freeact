from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

STDIO_SERVER_PATH = Path(__file__)


class InnerResult(BaseModel):
    """Inner nested result structure."""

    code: int = Field(description="Status code")
    details: str = Field(description="Detailed information")


class OuterResult(BaseModel):
    """Outer result structure containing nested data."""

    status: str = Field(description="Overall status of the operation")
    inner: InnerResult = Field(description="Nested result data")
    count: int = Field(description="Number of items processed")


async def tool_1(s: str) -> str:
    """
    This is tool 1.

    Args:
        s: A string
    """
    return f"You passed to tool 1: {s}"


async def tool_2(s: str) -> str:
    """
    This is tool 2.
    """
    return f"You passed to tool 2: {s}"


async def tool_3(name: str, level: int) -> OuterResult:
    """
    This is tool 3 with nested structured output.

    Args:
        name: A name to process
        level: Processing level
    """
    return OuterResult(
        status=f"completed_{name}",
        inner=InnerResult(
            code=level * 100,
            details=f"Processing {name} at level {level}",
        ),
        count=len(name),
    )


def create_server() -> FastMCP:
    server = FastMCP("Test MCP Server", log_level="ERROR")
    server.add_tool(tool_1, structured_output=False, name="tool-1")
    server.add_tool(tool_2, structured_output=False)
    server.add_tool(tool_3)
    return server


def main() -> None:
    server = create_server()

    try:
        server.run(transport="stdio")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
