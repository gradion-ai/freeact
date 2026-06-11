import asyncio
import json
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, TypeAlias

from textual.containers import Vertical
from textual.widgets import Static

from freeact.config import TerminalSection
from freeact.events import ApprovalRequest
from freeact.permissions import PermissionManager
from freeact.terminal.view import ConversationView, TrackedCollapsible
from freeact.terminal.widgets import ApprovalBar, create_action_box, diff_content, syntax_content
from freeact.toolcalls import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    ToolCall,
    parse_pattern,
    suggest_display,
    suggest_pattern,
)

if TYPE_CHECKING:
    from freeact.terminal.dispatcher import EventDispatcher

BoxBuild: TypeAlias = tuple[TrackedCollapsible, Vertical, bool]
"""Built tool-call widget: `(box, trace_container, is_subagent_task)`."""

BoxRenderer: TypeAlias = Callable[[Any, str], BoxBuild]


def _render_code_action(call: CodeAction, agent_id: str) -> BoxBuild:
    box, trace = create_action_box(
        syntax_content(call.code, "python"),
        title="Code Action",
        agent_id=agent_id,
        classes="code-action-box",
    )
    return box, trace, False


def _render_file_edit(call: FileEdit, agent_id: str) -> BoxBuild:
    box, trace = create_action_box(
        diff_content(call.path, call.old_text, call.new_text),
        title=f"Edit Action: {call.path}",
        agent_id=agent_id,
        classes="diff-box",
    )
    return box, trace, False


def _render_file_read(call: FileRead, agent_id: str) -> BoxBuild:
    filename = PurePosixPath(call.path).name
    parts: list[str] = [call.path]
    if call.offset is not None:
        parts.append(f"offset: {call.offset}")
    if call.limit is not None:
        parts.append(f"limit: {call.limit}")
    box, trace = create_action_box(
        Static("\n".join(parts)),
        title=f"Read Action: {filename}",
        agent_id=agent_id,
        classes="read-file-box",
    )
    return box, trace, False


def _render_file_write(call: FileWrite, agent_id: str) -> BoxBuild:
    ext = call.path.rsplit(".", 1)[-1] if "." in call.path else "text"
    box, trace = create_action_box(
        syntax_content(call.content, ext),
        title=f"Write Action: {call.path}",
        agent_id=agent_id,
        classes="write-file-box",
    )
    return box, trace, False


def _render_shell_action(call: ShellAction, agent_id: str) -> BoxBuild:
    title = "Shell Script" if call.tool_name == "shell_magic" else "Shell Command"
    box, trace = create_action_box(
        syntax_content(call.command, "bash"),
        title=title,
        agent_id=agent_id,
        classes="tool-call-box",
    )
    return box, trace, False


def _render_generic_call(call: GenericCall, agent_id: str) -> BoxBuild:
    args_json = json.dumps(call.tool_args, indent=2)
    if call.tool_name == "subagent_task":
        box, trace = create_action_box(
            syntax_content(args_json, "json"),
            title="Tool Call: subagent_task",
            agent_id=agent_id,
            classes="tool-call-box subagent-task-box",
        )
        return box, trace, True
    title_prefix = "PTC" if call.ptc else "Tool Call"
    box, trace = create_action_box(
        syntax_content(args_json, "json"),
        title=f"{title_prefix}: {call.tool_name}",
        agent_id=agent_id,
        classes="tool-call-box",
    )
    return box, trace, False


_RENDERERS: dict[type[ToolCall], BoxRenderer] = {
    CodeAction: _render_code_action,
    FileEdit: _render_file_edit,
    FileRead: _render_file_read,
    FileWrite: _render_file_write,
    ShellAction: _render_shell_action,
    GenericCall: _render_generic_call,
}


def build_tool_call_box(tool_call: ToolCall, agent_id: str) -> BoxBuild:
    """Create the widget used to present a pending tool approval.

    Args:
        tool_call: Tool call to render.
        agent_id: Agent identifier for the title prefix.

    Returns:
        Tuple of the box, its nested trace container, and whether the call
        is a `subagent_task`.
    """
    renderer = _RENDERERS.get(type(tool_call))
    if renderer is None:
        raise ValueError(f"Unsupported tool call: {tool_call!r}")
    return renderer(tool_call, agent_id)


class ApprovalController:
    """Approval flow for tool calls: box rendering, bar lifecycle, decisions."""

    def __init__(
        self,
        view: ConversationView,
        permissions: PermissionManager,
        config: TerminalSection,
        skip_permissions: bool = False,
    ) -> None:
        """Initialize the approval controller.

        Args:
            view: Conversation view used for mounting boxes and bars.
            permissions: Permission manager for pre-approval and rule storage.
            config: Terminal UI configuration.
            skip_permissions: Approve all tool calls without prompting.
        """
        self._view = view
        self._permissions = permissions
        self._config = config
        self._skip_permissions = skip_permissions
        self._approval_future: asyncio.Future[tuple[int, str]] | None = None
        self._bar: ApprovalBar | None = None

    @property
    def pending(self) -> bool:
        """Whether an approval decision is currently awaited."""
        return self._approval_future is not None and not self._approval_future.done()

    @property
    def bar_editing(self) -> bool:
        """Whether the current approval bar has an active pattern input."""
        return self._bar is not None and self._bar.editing

    @property
    def has_bar(self) -> bool:
        """Whether an approval bar is currently mounted."""
        return self._bar is not None

    async def handle(self, request: ApprovalRequest, dispatcher: "EventDispatcher") -> None:
        """Render the tool call, gather an approval decision, and resolve it.

        Pre-approved calls (permission match or skip-permissions) resolve
        immediately without showing the approval bar.

        Args:
            request: Pending approval request from the agent stream.
            dispatcher: Turn dispatcher owning the corr_id container map.
        """
        tc = request.tool_call
        target = dispatcher.target_for(request)
        box, trace_container, is_subagent_task = build_tool_call_box(tc, request.agent_id)
        tc_state = dispatcher.register(request.corr_id, box, trace_container, is_subagent_task)

        pin_pending = self._config.pin_pending_approval_action_expanded
        await self._view.mount_box(box, target=target, configured_collapsed=False, force_expanded=pin_pending)

        pre_approved = self._skip_permissions or self._permissions.is_allowed(tc)

        if pre_approved:
            if pin_pending:
                self._view.policy.set_forced(box, enabled=False)
            self._view.policy.set_configured(box, collapsed=self._collapse_for_approved_action(tc))
            if tc_state is not None and tc_state.is_subagent_task:
                dispatcher.mark_subagent_task_active(request.corr_id)
            request.approve(True)
            return

        # Prompt user for approval. The bar mounts at conversation root so
        # subagent approvals stay visible inside collapsed task boxes.
        self._approval_future = asyncio.get_running_loop().create_future()
        bar = ApprovalBar(pattern=suggest_pattern(tc), display_text=suggest_display(tc))
        self._bar = bar
        await self._view.mount_widgets(bar)

        decision, pattern = await self._approval_future
        self._approval_future = None
        self._bar = None

        await bar.remove()
        if pin_pending:
            self._view.policy.set_forced(box, enabled=False)

        match decision:
            case 2:
                await asyncio.to_thread(self._permissions.allow_always, parse_pattern(pattern, tc))
            case 3:
                self._permissions.allow_session(parse_pattern(pattern, tc))

        approved = decision != 0
        if approved:
            self._view.policy.set_configured(box, collapsed=self._collapse_for_approved_action(tc))
            if tc_state is not None and tc_state.is_subagent_task:
                dispatcher.mark_subagent_task_active(request.corr_id)
        else:
            self._view.policy.set_configured(box, collapsed=not self._config.keep_rejected_actions_expanded)
        request.approve(approved)

    def on_decided(self, decision: int, pattern: str) -> None:
        """Resolve the pending approval from an `ApprovalBar.Decided` message."""
        future = self._approval_future
        if future is not None and not future.done():
            future.set_result((decision, pattern))

    def resolve(self, decision: int) -> None:
        """Resolve the pending approval from an app-level hotkey."""
        future = self._approval_future
        if future is not None and not future.done():
            pattern = self._bar.pattern if self._bar is not None else ""
            future.set_result((decision, pattern))

    def open_rule_editor(self, scope: int) -> None:
        """Open the editable pattern input on the current approval bar."""
        if self._bar is not None:
            self._bar.action_save_rule(scope)

    def reject_pending(self) -> None:
        """Reject the pending approval, if any (used on turn cancellation)."""
        future = self._approval_future
        if future is not None and not future.done():
            future.set_result((0, ""))

    def _collapse_for_approved_action(self, tool_call: ToolCall) -> bool:
        match tool_call:
            case CodeAction():
                return self._config.collapse_approved_code_actions
            case GenericCall(tool_name="subagent_task"):
                return False
            case _:
                return self._config.collapse_approved_tool_calls
