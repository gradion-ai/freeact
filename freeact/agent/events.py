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

    def format(self, max_chars: int = 5000) -> str:
        """Format output with image markdown links, truncated to `max_chars`.

        Preserves 80% of characters from the start and 20% from the end
        when truncation is needed.
        """
        parts: list[str] = []
        if self.text:
            parts.append(self.text)
        for image_path in self.images:
            parts.append(f"![Image]({image_path})")
        formatted = "\n".join(parts) if parts else ""

        if len(formatted) <= max_chars:
            return formatted

        first_part_len = int(max_chars * 0.8)
        last_part_len = int(max_chars * 0.2) - 3

        return formatted[:first_part_len] + "..." + formatted[-last_part_len:]


@dataclass
class ApprovalRequest(AgentEvent):
    """Pending code action or tool call awaiting user approval.

    Yielded by [`Agent.stream()`][freeact.agent.Agent.stream] before
    executing any code action, programmatic tool call, or JSON tool call.
    The stream is suspended until `approve()` is called.
    """

    tool_name: str
    tool_args: dict[str, Any]
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
