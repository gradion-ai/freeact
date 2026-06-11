from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from textual.containers import Vertical
from textual.widgets import Markdown, RichLog

from freeact.config import TerminalSection
from freeact.events import (
    AgentEvent,
    ApprovalRequest,
    Cancelled,
    CodeExecutionOutput,
    CodeExecutionOutputChunk,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.terminal.approvals import ApprovalController
from freeact.terminal.view import ConversationView, TrackedCollapsible
from freeact.terminal.widgets import (
    create_box,
    create_exec_output_box,
    create_markdown_box,
    finalize_exec_output,
    syntax_content,
)
from freeact.toolcalls import extract_tool_output_text

ExecLogKey: TypeAlias = tuple[str, str, str]


@dataclass(frozen=True)
class ToolCallBoxState:
    """Mounted container state for a tool-call widget with nested trace container."""

    box: TrackedCollapsible
    trace_container: Vertical
    is_subagent_task: bool = False


@dataclass
class _MarkdownStreamState:
    """Live markdown stream with its owning box."""

    box: TrackedCollapsible
    stream: "Markdown.MarkdownStream"


@dataclass
class _ExecOutputState:
    """Mounted execution output state for a single execution stream."""

    box: TrackedCollapsible
    log: RichLog


class EventDispatcher:
    """Routes the agent events of one conversation turn into the view.

    Main-agent thoughts and responses stream into markdown boxes; execution
    output and tool output route to the container owning their correlation
    id (nesting subagent events inside their task box); approval requests
    are delegated to the approval controller. Owns the turn-scoped UI state.
    """

    def __init__(
        self,
        agent_id: str,
        view: ConversationView,
        approvals: ApprovalController,
        config: TerminalSection,
    ) -> None:
        """Initialize a dispatcher for one conversation turn.

        Args:
            agent_id: Identifier of the main agent.
            view: Conversation view used for mounting widgets.
            approvals: Approval controller handling `ApprovalRequest` events.
            config: Terminal UI configuration.
        """
        self._agent_id = agent_id
        self._view = view
        self._approvals = approvals
        self._config = config
        self._tool_call_boxes: dict[str, ToolCallBoxState] = {}
        self._thoughts: _MarkdownStreamState | None = None
        self._response: _MarkdownStreamState | None = None
        self._exec_logs: dict[ExecLogKey, _ExecOutputState] = {}

    def register(
        self,
        corr_id: str,
        box: TrackedCollapsible,
        trace_container: Vertical,
        is_subagent_task: bool = False,
    ) -> ToolCallBoxState | None:
        """Register a mounted tool-call box as the container for a correlation id.

        Args:
            corr_id: Correlation id owning the box; empty ids are ignored.
            box: Mounted tool-call collapsible.
            trace_container: Nested container receiving correlated events.
            is_subagent_task: Whether the box renders a `subagent_task` call.

        Returns:
            The registered (or previously registered) state, or `None` when
            `corr_id` is empty.
        """
        if not corr_id:
            return None
        if corr_id not in self._tool_call_boxes:
            self._tool_call_boxes[corr_id] = ToolCallBoxState(
                box=box,
                trace_container=trace_container,
                is_subagent_task=is_subagent_task,
            )
        return self._tool_call_boxes[corr_id]

    def target_for(self, event: AgentEvent) -> Vertical | None:
        """Resolve the trace container owning an event, if any.

        Routing priority: `corr_id`, then `parent_corr_id`, then `None`
        (conversation root).
        """
        state = self._resolve_tool_call_state(event.corr_id, event.parent_corr_id)
        if state is not None:
            return state.trace_container
        return None

    def mark_subagent_task_active(self, corr_id: str) -> None:
        """Pin a subagent task box expanded while the task is running."""
        state = self._tool_call_boxes.get(corr_id)
        if state is None:
            return
        self._view.policy.set_forced(state.box, enabled=True)

    def finish(self) -> None:
        """Release turn-scoped state at the end of a turn."""
        for state in self._tool_call_boxes.values():
            self._view.policy.set_forced(state.box, enabled=False)
        self._tool_call_boxes.clear()

    async def dispatch(self, event: AgentEvent) -> None:
        """Route a single agent event to the appropriate handler."""
        match event:
            case ThoughtsChunk(agent_id=aid, content=chunk) if aid == self._agent_id:
                await self._handle_main_thoughts_chunk(aid, chunk)
            case Thoughts(agent_id=aid) if aid == self._agent_id:
                await self._handle_main_thoughts_complete()
            case ResponseChunk(agent_id=aid, content=chunk) if aid == self._agent_id:
                await self._handle_main_response_chunk(aid, chunk)
            case Response(agent_id=aid) if aid == self._agent_id:
                await self._handle_main_response_complete()
            case ApprovalRequest() as request:
                await self._approvals.handle(request, self)
            case CodeExecutionOutputChunk(agent_id=aid, text=text, corr_id=cid, parent_corr_id=parent_cid):
                await self._handle_exec_output_chunk(aid, cid, parent_cid, text)
            case CodeExecutionOutput(agent_id=aid, text=text, images=images, corr_id=cid, parent_corr_id=parent_cid):
                await self._handle_exec_output(aid, cid, parent_cid, text, images)
            case ToolOutput(agent_id=aid, content=tool_content, corr_id=cid):
                await self._handle_tool_output(event, aid, cid, tool_content)
            case Cancelled():
                pass

    def _resolve_tool_call_state(self, corr_id: str, parent_corr_id: str) -> ToolCallBoxState | None:
        """Look up tool-call box state, trying corr_id first then parent_corr_id."""
        if corr_id:
            state = self._tool_call_boxes.get(corr_id)
            if state is not None:
                return state
        if parent_corr_id:
            return self._tool_call_boxes.get(parent_corr_id)
        return None

    def _mark_subagent_task_completed(self, corr_id: str) -> None:
        state = self._tool_call_boxes.get(corr_id)
        if state is None:
            return
        self._view.policy.set_forced(state.box, enabled=False)
        self._view.policy.set_configured(
            state.box,
            collapsed=self._config.collapse_completed_subagent_tasks,
        )

    async def _handle_main_thoughts_chunk(self, agent_id: str, chunk: str) -> None:
        if self._thoughts is None:
            box, md = create_markdown_box("Thinking", agent_id=agent_id, classes="thoughts-box")
            await self._view.mount_box(box)
            self._thoughts = _MarkdownStreamState(box=box, stream=Markdown.get_stream(md))
        await self._thoughts.stream.write(chunk)

    async def _handle_main_thoughts_complete(self) -> None:
        if self._thoughts is None:
            return
        await self._thoughts.stream.stop()
        box = self._thoughts.box
        self._thoughts = None
        if self._config.collapse_thoughts_on_complete:
            self._view.policy.set_configured(box, collapsed=True)

    async def _handle_main_response_chunk(self, agent_id: str, chunk: str) -> None:
        if self._response is None:
            box, md = create_markdown_box("Response", agent_id=agent_id, classes="response-box")
            await self._view.mount_box(box)
            self._response = _MarkdownStreamState(box=box, stream=Markdown.get_stream(md))
        await self._response.stream.write(chunk)

    async def _handle_main_response_complete(self) -> None:
        if self._response is None:
            return
        await self._response.stream.stop()
        self._response = None

    async def _ensure_exec_output_state(
        self,
        agent_id: str,
        corr_id: str,
        parent_corr_id: str,
    ) -> _ExecOutputState:
        exec_key = (agent_id, corr_id, parent_corr_id)
        existing = self._exec_logs.get(exec_key)
        if existing is not None:
            return existing

        box, exec_log = create_exec_output_box(agent_id)
        tc_state = self._resolve_tool_call_state(corr_id, parent_corr_id)
        target = tc_state.trace_container if tc_state is not None else None
        await self._view.mount_box(box, target=target)
        exec_state = _ExecOutputState(box=box, log=exec_log)
        self._exec_logs[exec_key] = exec_state
        return exec_state

    async def _handle_exec_output_chunk(
        self,
        agent_id: str,
        corr_id: str,
        parent_corr_id: str,
        text: str,
    ) -> None:
        exec_state = await self._ensure_exec_output_state(agent_id, corr_id, parent_corr_id)
        exec_state.log.write(text)
        self._view.schedule_scroll_to_latest()

    async def _handle_exec_output(
        self,
        agent_id: str,
        corr_id: str,
        parent_corr_id: str,
        text: str | None,
        images: list[Path],
    ) -> None:
        exec_state = await self._ensure_exec_output_state(agent_id, corr_id, parent_corr_id)
        await finalize_exec_output(exec_state.log, text, images)
        if self._config.collapse_exec_output_on_complete:
            self._view.policy.set_configured(exec_state.box, collapsed=True)
        self._view.schedule_scroll_to_latest()
        del self._exec_logs[(agent_id, corr_id, parent_corr_id)]

    async def _handle_tool_output(
        self,
        event: ToolOutput,
        agent_id: str,
        corr_id: str,
        tool_content: object,
    ) -> None:
        output_text = extract_tool_output_text(tool_content)
        box = create_box(
            syntax_content(output_text, "text"),
            title="Tool Output",
            agent_id=agent_id,
            collapsed=True,
            classes="tool-output-box",
        )
        await self._view.mount_box(
            box,
            target=self.target_for(event),
            configured_collapsed=self._config.collapse_tool_outputs,
        )
        state = self._tool_call_boxes.get(corr_id)
        if state is not None and state.is_subagent_task and not event.parent_corr_id:
            self._mark_subagent_task_completed(corr_id)
