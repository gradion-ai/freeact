import re
from asyncio import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai.mcp import ToolResult


@dataclass(kw_only=True)
class AgentEvent:
    """Base class for all agent stream events.

    Carries the `agent_id` of the agent that produced the event, allowing
    callers to distinguish events from a parent agent vs. its subagents.
    """

    agent_id: str = ""
    corr_id: str = ""


@dataclass
class ResponseChunk(AgentEvent):
    """Partial model response text (content streaming)."""

    content: str


@dataclass
class Response(AgentEvent):
    """Complete model response at a given step."""

    content: str


@dataclass
class ThoughtsChunk(AgentEvent):
    """Partial model thinking text (content streaming)."""

    content: str


@dataclass
class Thoughts(AgentEvent):
    """Complete model thoughts at a given step."""

    content: str


@dataclass
class ToolOutput(AgentEvent):
    """Tool or built-in operation output."""

    content: ToolResult


@dataclass
class CodeExecutionOutputChunk(AgentEvent):
    """Partial code execution output (content streaming)."""

    text: str


@dataclass
class CodeExecutionOutput(AgentEvent):
    """Complete code execution output."""

    text: str | None
    images: list[Path]

    def ptc_rejected(self) -> bool:
        """Whether the output indicates a rejected programmatic tool call."""
        if not self.text:
            return False

        # TODO: make detection of PTC rejection more robust ...
        pattern = r"ToolRunnerError: Approval request for \S+ rejected"
        return bool(re.search(pattern, self.text))

    def format(self) -> str:
        """Format output with image markdown links."""
        parts: list[str] = []
        if self.text:
            parts.append(self.text)
        for image_path in self.images:
            parts.append(f"![Image]({image_path})")
        return "\n".join(parts) if parts else ""


@dataclass
class ApprovalRequest(AgentEvent):
    """Pending code action or tool call awaiting user approval.

    Yielded by [`Agent.stream()`][freeact.agent.Agent.stream] before
    executing any code action, programmatic tool call, or JSON tool call.
    The stream is suspended until `approve()` is called.
    """

    tool_name: str
    tool_args: dict[str, Any]
    ptc: bool = False
    _future: Future[bool] = field(default_factory=Future)

    def approve(self, decision: bool) -> None:
        """Resolve this approval request.

        Args:
            decision: `True` to execute, `False` to reject and end
                the current agent turn.
        """
        self._future.set_result(decision)

    async def approved(self) -> bool:
        """Await until `approve()` is called and return the decision."""
        return await self._future
